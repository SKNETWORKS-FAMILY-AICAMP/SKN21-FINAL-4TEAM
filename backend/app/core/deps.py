from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token, get_user_session_jti, is_token_blacklisted
from app.core.database import get_db
from app.models.user import User

# auto_error=False: Authorization 헤더가 없어도 에러 미발생 (쿠키로 fallback)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT에서 현재 사용자를 추출한다. Authorization 헤더 또는 쿠키를 지원. 블랙리스트 토큰은 거부."""
    token = credentials.credentials if credentials else access_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # 토큰 블랙리스트 확인 (로그아웃된 토큰 차단)
    if await is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # 단일 세션 강제: jti가 있으면 Redis에 저장된 현재 세션 JTI와 비교
    jti = payload.get("jti")
    if jti:
        current_jti = await get_user_session_jti(user_id)
        # current_jti가 None이면 Redis 장애 → fail-open (서비스 중단 방지)
        if current_jti is not None and current_jti != jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired: logged in from another device",
                headers={"X-Error-Code": "AUTH_SESSION_REPLACED"},
            )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # 밴 상태 확인
    if user.banned_until is not None:
        if user.banned_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account banned until {user.banned_until.isoformat()}",
                headers={"X-Error-Code": "USER_BANNED"},
            )

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """관리자 역할(admin 또는 superadmin)만 통과시킨다."""
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_superadmin(user: User = Depends(get_current_user)) -> User:
    """슈퍼관리자 역할만 통과시킨다."""
    if user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return user



async def require_adult_verified(user: User = Depends(get_current_user)) -> User:
    """성인인증 완료 사용자만 통과시킨다."""
    if user.adult_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adult verification required",
            headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
        )
    return user
