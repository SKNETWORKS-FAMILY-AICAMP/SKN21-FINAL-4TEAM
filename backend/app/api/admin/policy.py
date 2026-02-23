from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.user import User

router = APIRouter()

# 프로토타입에서는 연령등급 정책을 메모리 내 설정으로 관리
_age_rating_policy = {
    "ratings": ["all", "12+", "15+", "18+"],
    "default": "all",
    "adult_verification_required": ["18+"],
    "enabled": True,
}


class AgeRatingPolicy(BaseModel):
    ratings: list[str]
    default: str
    adult_verification_required: list[str]
    enabled: bool


@router.get("/age-rating", response_model=AgeRatingPolicy)
async def get_age_rating_policy(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """연령등급 정책 조회."""
    return _age_rating_policy


@router.put("/age-rating", response_model=AgeRatingPolicy)
async def update_age_rating_policy(
    data: AgeRatingPolicy,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """연령등급 정책 수정."""
    global _age_rating_policy
    _age_rating_policy = data.model_dump()
    return _age_rating_policy
