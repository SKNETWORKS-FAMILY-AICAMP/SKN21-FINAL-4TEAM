"""수동 모드 승인 큐 API — 소유자가 AI 생성 콘텐츠를 검토/승인/거절."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.pending_post import PendingPostListResponse, PendingPostResponse
from app.services.pending_post_service import PendingPostService

router = APIRouter()


@router.get("/", response_model=PendingPostListResponse)
async def list_pending_posts(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 캐릭터 pending 목록."""
    svc = PendingPostService(db)
    data = await svc.list_by_owner(user.id, status_filter=status_filter, skip=skip, limit=limit)
    items = [
        PendingPostResponse(
            id=p.id,
            persona_id=p.persona_id,
            content_type=p.content_type,
            title=p.title,
            content=p.content,
            target_post_id=p.target_post_id,
            target_comment_id=p.target_comment_id,
            status=p.status,
            input_tokens=p.input_tokens,
            output_tokens=p.output_tokens,
            cost=float(p.cost),
            created_at=p.created_at,
            reviewed_at=p.reviewed_at,
        )
        for p in data["items"]
    ]
    return PendingPostListResponse(items=items, total=data["total"])


@router.post("/{pending_id}/approve")
async def approve_pending_post(
    pending_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """승인 — pending → board_posts/board_comments로 발행."""
    svc = PendingPostService(db)
    result = await svc.approve(pending_id, user)
    return {"status": "approved", "id": str(result.id)}


@router.post("/{pending_id}/reject")
async def reject_pending_post(
    pending_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """거절 — 환불 없음 (LLM 호출 비용 이미 발생)."""
    svc = PendingPostService(db)
    result = await svc.reject(pending_id, user)
    return {"status": "rejected", "id": str(result.id)}
