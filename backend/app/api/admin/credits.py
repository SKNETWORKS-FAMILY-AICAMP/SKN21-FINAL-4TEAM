from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.user import User
from app.schemas.credit import AdminCreditGrantRequest, AdminCreditSummary, CreditCostItem
from app.services.credit_service import CreditService

router = APIRouter()


@router.get("/summary", response_model=AdminCreditSummary)
async def get_credit_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 크레딧 경제 통계."""
    service = CreditService(db)
    return await service.get_admin_summary()


@router.put("/grant")
async def grant_credits(
    data: AdminCreditGrantRequest,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """특정 유저에게 크레딧 지급."""
    service = CreditService(db)
    ledger = await service.admin_grant(data.user_id, data.amount, data.description)
    return {"id": ledger.id, "amount": ledger.amount, "balance_after": ledger.balance_after}


@router.get("/costs", response_model=list[CreditCostItem])
async def get_costs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """현재 대화석 소비 단가표."""
    service = CreditService(db)
    return await service.get_cost_table()
