from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.schemas.debate_topic import TopicUpdate
from app.services.debate_match_service import DebateMatchService
from app.services.debate_topic_service import DebateTopicService

router = APIRouter()


@router.get("/stats")
async def debate_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토론 플랫폼 전체 통계."""
    agents_count = (await db.execute(select(func.count(DebateAgent.id)))).scalar() or 0
    topics_count = (await db.execute(select(func.count(DebateTopic.id)))).scalar() or 0
    matches_total = (await db.execute(select(func.count(DebateMatch.id)))).scalar() or 0
    matches_completed = (await db.execute(
        select(func.count(DebateMatch.id)).where(DebateMatch.status == "completed")
    )).scalar() or 0
    matches_in_progress = (await db.execute(
        select(func.count(DebateMatch.id)).where(DebateMatch.status == "in_progress")
    )).scalar() or 0

    return {
        "agents_count": agents_count,
        "topics_count": topics_count,
        "matches_total": matches_total,
        "matches_completed": matches_completed,
        "matches_in_progress": matches_in_progress,
    }


@router.patch("/topics/{topic_id}")
async def update_topic(
    topic_id: str,
    data: TopicUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토픽 수정 (관리자)."""
    service = DebateTopicService(db)
    try:
        topic = await service.update_topic(topic_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {
        "id": str(topic.id),
        "title": topic.title,
        "status": topic.status,
        "updated_at": topic.updated_at,
    }


@router.get("/matches")
async def list_all_matches(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 매치 목록 (관리자)."""
    service = DebateMatchService(db)
    items, total = await service.list_matches(status=status_filter, skip=skip, limit=limit)
    return {"items": items, "total": total}
