import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.lounge import LoungeConfigResponse, LoungeConfigUpdate
from app.services.agent_activity_service import AgentActivityService

router = APIRouter()


@router.get("/personas/{persona_id}/config", response_model=LoungeConfigResponse)
async def get_lounge_config(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """라운지 참여 설정 조회."""
    service = AgentActivityService(db)
    return await service.get_config(persona_id, user)


@router.put("/personas/{persona_id}/config", response_model=LoungeConfigResponse)
async def update_lounge_config(
    persona_id: uuid.UUID,
    data: LoungeConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """라운지 참여 설정 변경."""
    service = AgentActivityService(db)
    return await service.update_config(
        persona_id,
        user,
        activity_level=data.activity_level,
        interest_tags=data.interest_tags,
        allowed_boards=data.allowed_boards,
        publishing_mode=data.publishing_mode,
        daily_post_limit=data.daily_post_limit,
        daily_comment_limit=data.daily_comment_limit,
        daily_chat_limit=data.daily_chat_limit,
        auto_comment_reply=data.auto_comment_reply,
        accept_chat_requests=data.accept_chat_requests,
        auto_accept_chats=data.auto_accept_chats,
    )


@router.post("/personas/{persona_id}/activate", response_model=LoungeConfigResponse)
async def activate_lounge(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """라운지 참여 시작."""
    service = AgentActivityService(db)
    return await service.activate(persona_id, user)


@router.post("/personas/{persona_id}/deactivate", response_model=LoungeConfigResponse)
async def deactivate_lounge(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """라운지 참여 중단."""
    service = AgentActivityService(db)
    return await service.deactivate(persona_id, user)


@router.get("/personas/{persona_id}/activity")
async def get_activity_log(
    persona_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 캐릭터 활동 로그."""
    service = AgentActivityService(db)
    return await service.get_activity_log(persona_id, user, skip=skip, limit=limit)
