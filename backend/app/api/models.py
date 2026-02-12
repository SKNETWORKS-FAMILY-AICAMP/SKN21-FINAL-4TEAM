from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/")
async def list_available_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용 가능한 LLM 모델 목록."""
    raise NotImplementedError


@router.put("/preferred")
async def set_preferred_model(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """선호 LLM 모델 변경."""
    raise NotImplementedError
