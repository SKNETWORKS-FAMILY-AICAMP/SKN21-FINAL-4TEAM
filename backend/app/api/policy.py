from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/spoiler/{webtoon_id}")
async def get_spoiler_setting(
    webtoon_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 스포일러 설정 조회."""
    raise NotImplementedError


@router.put("/spoiler/{webtoon_id}")
async def update_spoiler_setting(
    webtoon_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """스포일러 설정 변경."""
    raise NotImplementedError
