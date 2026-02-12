import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.policy_service import PolicyService

router = APIRouter()


class SpoilerUpdate(BaseModel):
    mode: str
    max_episode: int | None = None


@router.get("/spoiler/{webtoon_id}")
async def get_spoiler_setting(
    webtoon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 스포일러 설정 조회."""
    service = PolicyService(db)
    return await service.get_spoiler_setting(user, webtoon_id)


@router.put("/spoiler/{webtoon_id}")
async def update_spoiler_setting(
    webtoon_id: uuid.UUID,
    data: SpoilerUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """스포일러 설정 변경."""
    service = PolicyService(db)
    return await service.update_spoiler_setting(user, webtoon_id, data.mode, data.max_episode)
