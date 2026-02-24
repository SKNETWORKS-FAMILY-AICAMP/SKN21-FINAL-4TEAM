import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_match_queue import DebateMatchQueue
from app.models.user import User
from app.schemas.debate_match import JoinQueueRequest
from app.schemas.debate_topic import TopicCreate, TopicListResponse, TopicResponse
from app.services.debate_engine import run_debate
from app.services.debate_matching_service import DebateMatchingService
from app.services.debate_queue_broadcast import publish_queue_event, subscribe_queue
from app.services.debate_topic_service import DebateTopicService

router = APIRouter()


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    data: TopicCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토론 주제 생성. 관리자는 스케줄 설정 가능, 일반 유저는 즉시 open."""
    # 일반 유저가 스케줄 필드를 보내도 서비스에서 무시함
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
    user: User = Depends(get_current_user),
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


@router.get("/{topic_id}/queue/stream")
async def queue_stream(
    topic_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대기방 SSE 스트림. 매치/타임아웃/취소 이벤트를 수신."""
    # 에이전트 소유권 검증
    agent_result = await db.execute(
        select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not owned by user")

    # 큐 등록 여부 검증
    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    if queue_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent not in queue")

    return StreamingResponse(
        subscribe_queue(topic_id, agent_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{topic_id}/queue/status")
async def queue_status(
    topic_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 큐 상태 조회."""
    # 에이전트 소유권 검증
    agent_result = await db.execute(
        select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not owned by user")

    # 큐 엔트리 확인
    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    entry = queue_result.scalar_one_or_none()
    if entry is not None:
        # 큐 내 대기 위치 계산
        pos_result = await db.execute(
            select(DebateMatchQueue)
            .where(DebateMatchQueue.topic_id == topic_id)
            .order_by(DebateMatchQueue.joined_at)
        )
        all_entries = list(pos_result.scalars().all())
        position = next((i + 1 for i, e in enumerate(all_entries) if str(e.agent_id) == agent_id), 1)
        return {"status": "queued", "position": position, "joined_at": entry.joined_at.isoformat()}

    # 이미 매칭됐는지 확인 (최근 매치)
    match_result = await db.execute(
        select(DebateMatch).where(
            DebateMatch.topic_id == topic_id,
            (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id),
        ).order_by(DebateMatch.created_at.desc()).limit(1)
    )
    match = match_result.scalar_one_or_none()
    if match is not None:
        return {"status": "matched", "match_id": str(match.id)}

    return {"status": "not_in_queue"}


@router.delete("/{topic_id}/queue")
async def leave_queue(
    topic_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """큐 탈퇴. 대기 취소 이벤트 발행."""
    # 에이전트 소유권 검증
    agent_result = await db.execute(
        select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not owned by user")

    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    entry = queue_result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in queue")

    await db.delete(entry)
    await db.commit()

    await publish_queue_event(topic_id, agent_id, "cancelled", {})
    return {"status": "left"}


def _topic_response(topic) -> dict:
    return {
        "id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "mode": topic.mode,
        "status": topic.status,
        "max_turns": topic.max_turns,
        "turn_token_limit": topic.turn_token_limit,
        "scheduled_start_at": topic.scheduled_start_at,
        "scheduled_end_at": topic.scheduled_end_at,
        "is_admin_topic": topic.is_admin_topic,
        "tools_enabled": topic.tools_enabled,
        "queue_count": 0,
        "match_count": 0,
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
    }
