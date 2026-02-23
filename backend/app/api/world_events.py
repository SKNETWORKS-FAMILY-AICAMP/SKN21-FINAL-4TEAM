"""공개 세계관 이벤트 API — 사용자가 활성 이벤트를 조회."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.world_event import WorldEventResponse
from app.services.world_event_service import WorldEventService

router = APIRouter()


@router.get("/active", response_model=list[WorldEventResponse])
async def get_active_world_events(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 활성 세계관 이벤트 목록."""
    # 사용자 연령등급에 맞는 이벤트만
    age_filter = "all"
    if user.adult_verified_at:
        age_filter = "18+"
    elif hasattr(user, "age_group") and user.age_group == "minor_safe":
        age_filter = "15+"

    svc = WorldEventService(db)
    return await svc.get_active_events(age_filter)
