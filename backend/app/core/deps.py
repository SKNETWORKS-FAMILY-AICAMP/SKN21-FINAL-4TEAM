from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token, is_token_blacklisted
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT에서 현재 사용자를 추출한다. 블랙리스트 토큰은 거부."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # 토큰 블랙리스트 확인 (로그아웃된 토큰 차단)
    if await is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

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


async def require_developer(user: User = Depends(get_current_user)) -> User:
    """개발자 이상 역할(developer/admin/superadmin)만 통과시킨다."""
    if user.role not in ("developer", "admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer access required",
            headers={"X-Error-Code": "DEBATE_DEVELOPER_REQUIRED"},
        )
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
