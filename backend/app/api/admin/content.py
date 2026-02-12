from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.post("/webtoons")
async def create_webtoon(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """웹툰 등록."""
    raise NotImplementedError


@router.post("/webtoons/{webtoon_id}/episodes")
async def create_episode(
    webtoon_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """회차 등록."""
    raise NotImplementedError


@router.post("/live2d-models")
async def upload_live2d_model(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Live2D 모델 에셋 업로드."""
    raise NotImplementedError
