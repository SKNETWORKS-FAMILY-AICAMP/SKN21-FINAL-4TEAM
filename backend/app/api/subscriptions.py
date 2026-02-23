from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.subscription import PlanResponse, SubscribeRequest
from app.services.subscription_service import SubscriptionService

router = APIRouter()


@router.get("/plans", response_model=list[PlanResponse])
async def get_plans(db: AsyncSession = Depends(get_db)):
    """구독 플랜 목록."""
    service = SubscriptionService(db)
    return await service.get_plans()


@router.get("/me")
async def get_my_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 구독 상태."""
    service = SubscriptionService(db)
    sub = await service.get_my_subscription(user.id)
    if sub is None:
        return {"status": "none", "plan_key": "free"}
    return sub


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    data: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """구독 시작. 프로토타입에서는 실제 결제 없이 즉시 활성화."""
    service = SubscriptionService(db)
    sub = await service.subscribe(user.id, data.plan_key)
    return {"id": sub.id, "status": sub.status, "started_at": sub.started_at, "expires_at": sub.expires_at}


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """구독 해지."""
    service = SubscriptionService(db)
    sub = await service.cancel(user.id)
    return {"id": sub.id, "status": sub.status, "cancelled_at": sub.cancelled_at}
