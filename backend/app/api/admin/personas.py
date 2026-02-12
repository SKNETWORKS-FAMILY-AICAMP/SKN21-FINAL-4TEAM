import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.persona import PersonaListResponse, PersonaResponse
from app.services.moderation_service import ModerationService

router = APIRouter()


class ModerationAction(BaseModel):
    action: str  # "approved" or "blocked"


@router.get("/", response_model=PersonaListResponse)
async def list_personas_for_moderation(
    moderation_status: str = Query("pending"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """모더레이션 대기 페르소나 목록."""
    service = ModerationService(db)
    return await service.get_moderation_queue(moderation_status, skip=skip, limit=limit)


@router.put("/{persona_id}/moderation", response_model=PersonaResponse)
async def update_moderation_status(
    persona_id: uuid.UUID,
    data: ModerationAction,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 모더레이션 상태 변경 (approve/block)."""
    service = ModerationService(db)
    return await service.review_persona(persona_id, data.action)
