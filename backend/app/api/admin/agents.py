from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.lounge import AdminAgentSummary
from app.services.agent_activity_service import AgentActivityService

router = APIRouter()


@router.get("/activity", response_model=AdminAgentSummary)
async def admin_agent_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 에이전트 활동 통계."""
    service = AgentActivityService(db)
    return await service.get_admin_summary()


@router.get("/costs")
async def admin_agent_costs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 LLM 비용 통계 (페르소나별)."""
    service = AgentActivityService(db)
    return await service.get_admin_cost_stats()
