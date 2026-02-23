import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_developer
from app.models.user import User
from app.schemas.debate_match import JoinQueueRequest
from app.schemas.debate_topic import TopicCreate, TopicListResponse, TopicResponse
from app.services.debate_engine import run_debate
from app.services.debate_matching_service import DebateMatchingService
from app.services.debate_topic_service import DebateTopicService

router = APIRouter()


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    data: TopicCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토론 주제 생성 (관리자 전용)."""
    service = DebateTopicService(db)
    topic = await service.create_topic(data, user)
    return _topic_response(topic)


@router.get("", response_model=TopicListResponse)
async def list_topics(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateTopicService(db)
    items, total = await service.list_topics(status=status_filter, skip=skip, limit=limit)
    return {"items": items, "total": total}


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateTopicService(db)
    topic = await service.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return _topic_response(topic)


@router.post("/{topic_id}/join")
async def join_topic_queue(
    topic_id: str,
    data: JoinQueueRequest,
    user: User = Depends(require_developer),
    db: AsyncSession = Depends(get_db),
):
    """토픽 큐 참가. 2명 도달 시 자동 매치 생성."""
    service = DebateMatchingService(db)
    try:
        result = await service.join_queue(user, topic_id, data.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # 매치가 생성되었으면 백그라운드에서 토론 엔진 시작
    if result.get("status") == "matched" and result.get("match_id"):
        asyncio.create_task(run_debate(result["match_id"]))

    return result


def _topic_response(topic) -> dict:
    return {
        "id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "mode": topic.mode,
        "status": topic.status,
        "max_turns": topic.max_turns,
        "turn_token_limit": topic.turn_token_limit,
        "queue_count": 0,
        "match_count": 0,
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
    }
