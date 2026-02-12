from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def list_webtoons(db: AsyncSession = Depends(get_db)):
    """웹툰 목록 조회."""
    raise NotImplementedError


@router.get("/{webtoon_id}")
async def get_webtoon(webtoon_id: str, db: AsyncSession = Depends(get_db)):
    """웹툰 상세 + 회차 목록."""
    raise NotImplementedError


@router.get("/{webtoon_id}/episodes/{episode_number}")
async def get_episode(webtoon_id: str, episode_number: int, db: AsyncSession = Depends(get_db)):
    """회차 상세."""
    raise NotImplementedError
