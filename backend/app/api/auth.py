from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.adult_verify_service import AdultVerifyService
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """사용자 회원가입 → JWT 발급."""
    service = UserService(db)
    try:
        user = await service.create_user(data)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname already taken",
        )
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


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """현재 로그인 사용자 정보."""
    return user


class AdultVerifyRequest(BaseModel):
    method: str = "self_declare"


@router.post("/adult-verify", response_model=UserResponse)
async def adult_verify(
    data: AdultVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """성인인증 처리."""
    service = AdultVerifyService(db)
    await service.verify(user, data.method)
    await db.refresh(user)
    return user
