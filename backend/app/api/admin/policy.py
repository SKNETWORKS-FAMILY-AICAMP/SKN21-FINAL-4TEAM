from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/age-rating")
async def get_age_rating_policy(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """연령등급 정책 조회."""
    raise NotImplementedError


@router.put("/age-rating")
async def update_age_rating_policy(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """연령등급 정책 수정."""
    raise NotImplementedError
