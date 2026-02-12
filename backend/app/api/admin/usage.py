from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/summary")
async def get_usage_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 사용량 통계."""
    raise NotImplementedError


@router.get("/users/{user_id}")
async def get_user_usage(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """특정 사용자 상세 사용량."""
    raise NotImplementedError
