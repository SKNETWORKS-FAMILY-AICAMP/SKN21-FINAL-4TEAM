from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.subscription import AdminSubscriptionSummary
from app.services.subscription_service import SubscriptionService

router = APIRouter()


@router.get("/summary", response_model=AdminSubscriptionSummary)
async def get_subscription_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """구독 통계."""
    service = SubscriptionService(db)
    return await service.get_admin_summary()
