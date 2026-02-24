from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import blacklist_token, create_access_token
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import PasswordChange, TokenResponse, UserCreate, UserLogin, UserResponse, UserUpdate
from app.services.adult_verify_service import AdultVerifyService
from app.services.user_service import UserService

_bearer = HTTPBearer()

router = APIRouter()


@router.get("/check-nickname")
async def check_nickname(nickname: str, db: AsyncSession = Depends(get_db)):
    """닉네임 사용 가능 여부 확인."""
    service = UserService(db)
    available = await service.check_nickname_available(nickname)
    return {"available": available}


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """사용자 회원가입 → JWT 발급."""
    # 관리자 사칭 방지 — 일반 가입에서 'admin' 포함 닉네임 차단
    if "admin" in data.nickname.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nickname cannot contain 'admin'",
        )
    service = UserService(db)
    try:
        user = await service.create_user(data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname already taken",
        ) from None
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """로그인 → JWT 발급."""
    service = UserService(db)
    user = await service.authenticate(data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """로그아웃. 현재 토큰을 블랙리스트에 추가하여 재사용 차단."""
    await blacklist_token(credentials.credentials)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """현재 로그인 사용자 정보."""
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로필 정보 수정 (닉네임)."""
    # 일반 유저가 'admin' 포함 닉네임으로 변경하는 것 차단
    if data.nickname and "admin" in data.nickname.lower() and user.role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nickname cannot contain 'admin'",
        )
    service = UserService(db)
    try:
        updated = await service.update_profile(user, data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname already taken",
        ) from None
    return updated


@router.put("/me/password")
async def change_password(
    data: PasswordChange,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경. 성공 시 현재 토큰 무효화 + 새 토큰 발급."""
    service = UserService(db)
    success = await service.change_password(user, data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    # 현재 토큰 무효화
    await blacklist_token(credentials.credentials)
    # 새 토큰 발급
    new_token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"message": "Password changed successfully", "access_token": new_token}


class AdultVerifyRequest(BaseModel):
    method: str = "self_declare"
    # 테스트용 추가 필드 (method에 따라 선택적 사용)
    birth_year: int | None = None
    phone_number: str | None = None
    code: str | None = None
    card_last4: str | None = None


@router.post("/adult-verify")
async def adult_verify(
    data: AdultVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """성인인증 처리."""
    extra = {
        k: v
        for k, v in {
            "birth_year": data.birth_year,
            "phone_number": data.phone_number,
            "code": data.code,
            "card_last4": data.card_last4,
        }.items()
        if v is not None
    }
    service = AdultVerifyService(db)
    result = await service.verify(user, data.method, extra=extra)
    return result


@router.get("/adult-verify/status")
async def adult_verify_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """성인인증 상태 확인."""
    service = AdultVerifyService(db)
    return await service.check_status(user)


@router.post("/adult-verify/revoke")
async def adult_verify_revoke(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """성인인증 철회."""
    service = AdultVerifyService(db)
    return await service.revoke(user)


@router.get("/consent-history")
async def consent_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 동의 이력 조회."""
    service = AdultVerifyService(db)
    return await service.get_consent_history(user.id)
