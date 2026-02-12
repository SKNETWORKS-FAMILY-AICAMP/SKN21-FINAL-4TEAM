import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.usage_service import UsageService

router = APIRouter()


@router.get("/summary")
async def get_usage_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 사용량 통계."""
    service = UsageService(db)
    return await service.get_admin_summary()


@router.get("/users/{user_id}")
async def get_user_usage(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """특정 사용자 상세 사용량."""
    service = UsageService(db)
    return await service.get_user_usage_admin(user_id)
