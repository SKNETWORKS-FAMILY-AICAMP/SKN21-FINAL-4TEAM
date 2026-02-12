from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.post("/register")
async def register(db: AsyncSession = Depends(get_db)):
    """사용자 회원가입."""
    raise NotImplementedError


@router.post("/login")
async def login(db: AsyncSession = Depends(get_db)):
    """로그인 → JWT 발급."""
    raise NotImplementedError


@router.post("/adult-verify")
async def adult_verify(db: AsyncSession = Depends(get_db)):
    """성인인증 처리."""
    raise NotImplementedError
