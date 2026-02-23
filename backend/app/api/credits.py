from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.credit import (
    CreditBalanceResponse,
    CreditCostItem,
    CreditPurchaseRequest,
    CreditPurchaseResponse,
)
from app.services.credit_service import CreditService

router = APIRouter()


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 대화석 잔액 조회. 미충전 시 자동 일일 충전."""
    service = CreditService(db)
    await service.grant_daily_credits(user.id)
    await db.commit()
    return await service.get_balance(user.id)


@router.get("/history")
async def get_credit_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대화석 거래 내역."""
    service = CreditService(db)
    return await service.get_history(user.id, skip=skip, limit=limit)


@router.get("/costs", response_model=list[CreditCostItem])
async def get_credit_costs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """행동별 대화석 소비 단가표."""
    service = CreditService(db)
    return await service.get_cost_table()


@router.post("/purchase", response_model=CreditPurchaseResponse)
async def purchase_credits(
    data: CreditPurchaseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대화석 구매. 프로토타입에서는 실제 결제 없이 즉시 충전."""
    service = CreditService(db)
    return await service.purchase_credits(user.id, data.package)
