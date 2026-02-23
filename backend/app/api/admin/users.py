import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.persona import Persona
from app.models.user import User
from app.models.user_subscription import UserSubscription
from app.schemas.user import (
    AdminUserDetailResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    UserResponse,
    UserStats,
)

router = APIRouter()


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    stats: UserStats | None = None


class RoleUpdate(BaseModel):
    role: str


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=50),
    role: str | None = Query(None),
    age_group: str | None = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 목록 (서버사이드 검색/필터 + 통계)."""
    # 필터 조건 빌드
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        query = query.where(User.nickname.ilike(f"%{search}%"))
        count_query = count_query.where(User.nickname.ilike(f"%{search}%"))
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if age_group:
        query = query.where(User.age_group == age_group)
        count_query = count_query.where(User.age_group == age_group)

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.order_by(User.created_at.desc()).offset(skip).limit(limit))
    items = result.scalars().all()

    # 전체 통계 (필터 무관, 항상 전역 수치)
    stats_result = await db.execute(
        select(
            func.count().label("total_users"),
            func.count().filter(User.role == "superadmin").label("superadmin_count"),
            func.count().filter(User.role == "admin").label("admin_count"),
            func.count().filter(User.age_group == "adult_verified").label("adult_verified_count"),
            func.count().filter(User.age_group == "unverified").label("unverified_count"),
            func.count().filter(User.age_group == "minor_safe").label("minor_safe_count"),
        ).select_from(User)
    )
    row = stats_result.one()
    stats = UserStats(
        total_users=row.total_users,
        superadmin_count=row.superadmin_count,
        admin_count=row.admin_count,
        adult_verified_count=row.adult_verified_count,
        unverified_count=row.unverified_count,
        minor_safe_count=row.minor_safe_count,
    )

    return {"items": list(items), "total": total, "stats": stats}


# bulk-delete를 {user_id} 보다 먼저 등록 (경로 충돌 방지)
@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_users(
    data: BulkDeleteRequest,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 일괄 삭제. 관리자 계정은 삭제 불가."""
    if not data.user_ids:
        return BulkDeleteResponse(deleted_count=0, skipped_admin_ids=[])

    # 요청자 자신 제거
    target_ids = [uid for uid in data.user_ids if uid != admin.id]

    # admin/superadmin 역할 사용자 조회 (삭제 보호)
    admin_result = await db.execute(
        select(User.id).where(User.id.in_(target_ids), User.role.in_(("admin", "superadmin")))
    )
    admin_ids = [row[0] for row in admin_result.all()]
    skipped = [uid for uid in data.user_ids if uid == admin.id] + admin_ids

    # 삭제 대상 = target_ids - admin_ids
    delete_ids = [uid for uid in target_ids if uid not in admin_ids]
    if not delete_ids:
        return BulkDeleteResponse(deleted_count=0, skipped_admin_ids=skipped)

    result = await db.execute(delete(User).where(User.id.in_(delete_ids)))
    await db.commit()

    return BulkDeleteResponse(
        deleted_count=result.rowcount,
        skipped_admin_ids=skipped,
    )


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 상세 정보 (관계 카운트 포함)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 관계 카운트
    persona_count = (
        await db.execute(select(func.count()).select_from(Persona).where(Persona.created_by == user_id))
    ).scalar()

    session_count = (
        await db.execute(select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id))
    ).scalar()

    message_count = (
        await db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.user_id == user_id)
        )
    ).scalar()

    # 최신 구독 상태
    sub_result = await db.execute(
        select(UserSubscription.status)
        .where(UserSubscription.user_id == user_id)
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    sub_status = sub_result.scalar_one_or_none()

    return AdminUserDetailResponse(
        id=user.id,
        nickname=user.nickname,
        role=user.role,
        age_group=user.age_group,
        adult_verified_at=user.adult_verified_at,
        preferred_llm_model_id=user.preferred_llm_model_id,
        preferred_themes=user.preferred_themes,
        credit_balance=user.credit_balance,
        last_credit_grant_at=user.last_credit_grant_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        persona_count=persona_count or 0,
        session_count=session_count or 0,
        message_count=message_count or 0,
        subscription_status=sub_status,
    )


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    data: RoleUpdate,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 역할 변경 (superadmin 전용)."""
    if data.role not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = data.role
    await db.commit()
    await db.refresh(user)
    return user
