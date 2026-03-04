import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.usage_quota import UsageQuota
from app.models.user import User
from app.services.quota_service import QuotaService
from app.services.usage_service import UsageService

router = APIRouter()


class QuotaUpdate(BaseModel):
    daily_token_limit: int | None = Field(None, ge=0, description="일일 토큰 한도")
    monthly_token_limit: int | None = Field(None, ge=0, description="월간 토큰 한도")
    monthly_cost_limit: float | None = Field(None, ge=0, description="월간 비용 한도 ($)")
    is_active: bool | None = Field(None, description="할당 활성 여부")


class QuotaResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    nickname: str | None = None
    daily_token_limit: int
    monthly_token_limit: int
    monthly_cost_limit: float
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/summary")
async def get_usage_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 사용량 통계."""
    service = UsageService(db)
    return await service.get_admin_summary()


@router.get("/users/{user_id}")
async def get_user_usage(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """특정 사용자 상세 사용량."""
    service = UsageService(db)
    return await service.get_user_usage_admin(user_id)


@router.get("/quotas", response_model=list[QuotaResponse])
async def list_quotas(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """모든 사용자 할당 목록 조회 (닉네임 포함)."""
    result = await db.execute(
        select(UsageQuota, User.nickname)
        .join(User, User.id == UsageQuota.user_id, isouter=True)
        .order_by(UsageQuota.created_at.desc())
    )
    rows = result.all()
    return [
        QuotaResponse(
            id=q.id,
            user_id=q.user_id,
            nickname=nickname,
            daily_token_limit=q.daily_token_limit,
            monthly_token_limit=q.monthly_token_limit,
            monthly_cost_limit=q.monthly_cost_limit,
            is_active=q.is_active,
        )
        for q, nickname in rows
    ]


@router.put("/quotas/{user_id}", response_model=QuotaResponse)
async def set_user_quota(
    user_id: uuid.UUID,
    data: QuotaUpdate,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 할당 설정/업데이트 (관리자 전용)."""
    # 대상 사용자 존재 확인
    user_result = await db.execute(select(User).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    service = QuotaService(db)
    quota = await service.set_user_quota(
        user_id=user_id,
        daily_limit=data.daily_token_limit,
        monthly_limit=data.monthly_token_limit,
        cost_limit=data.monthly_cost_limit,
        is_active=data.is_active,
    )
    return quota


class UserSearchResult(BaseModel):
    id: uuid.UUID
    nickname: str
    login_id: str


@router.get("/user-search", response_model=list[UserSearchResult])
async def search_users_for_quota(
    q: str = Query(..., min_length=1, max_length=50),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """닉네임/로그인ID로 사용자 검색 (쿼터 설정용)."""
    result = await db.execute(
        select(User.id, User.nickname, User.login_id)
        .where(
            or_(
                User.nickname.ilike(f"%{q}%"),
                User.login_id.ilike(f"%{q}%"),
            )
        )
        .limit(10)
    )
    rows = result.all()
    return [UserSearchResult(id=r.id, nickname=r.nickname, login_id=r.login_id) for r in rows]
