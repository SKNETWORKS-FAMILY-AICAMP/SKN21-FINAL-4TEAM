from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/me")
async def get_my_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 토큰 사용량 요약 (일/월/총계)."""
    raise NotImplementedError


@router.get("/me/history")
async def get_my_usage_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """일별 사용량 히스토리 (차트용)."""
    raise NotImplementedError
