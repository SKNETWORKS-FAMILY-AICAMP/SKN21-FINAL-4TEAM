import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_match_queue import DebateMatchQueue
from app.models.user import User
from app.schemas.debate_match import JoinQueueRequest
from app.schemas.debate_topic import TopicCreate, TopicListResponse, TopicResponse, TopicUpdatePayload
from app.services.debate_engine import run_debate
from app.services.debate_matching_service import DebateMatchingService
from app.services.debate_queue_broadcast import publish_queue_event, subscribe_queue
from app.services.debate_topic_service import DebateTopicService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    data: TopicCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토론 주제 생성. 모든 사용자가 스케줄 설정 가능, 관리자 여부는 is_admin_topic 플래그로만 구분."""
    service = DebateTopicService(db)
    try:
        topic = await service.create_topic(data, user)
    except ValueError as exc:
        detail = str(exc)
        if "한도" in detail:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return _topic_response(topic)


@router.get("", response_model=TopicListResponse)
async def list_topics(
    status_filter: str | None = Query(None, alias="status", pattern="^(scheduled|open|in_progress|closed)$"),
    sort: str = Query("recent", pattern="^(recent|popular_week|queue|matches)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateTopicService(db)
    items, total = await service.list_topics(status=status_filter, sort=sort, page=page, page_size=page_size)
    return {"items": items, "total": total}


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: UUID,
    payload: TopicUpdatePayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """주제 작성자가 자신의 주제를 수정."""
    service = DebateTopicService(db)
    try:
        topic = await service.update_topic_by_user(topic_id, user.id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _topic_response(topic)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """주제 작성자가 자신의 주제를 삭제. 진행 중 매치가 있으면 409 반환."""
    service = DebateTopicService(db)
    try:
        await service.delete_topic_by_user(topic_id, user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


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
    queue_count = await service._count_queue(topic.id)
    match_count = await service._count_matches(topic.id)
    return _topic_response(topic, queue_count=queue_count, match_count=match_count)


async def _run_debate_safe(match_id: str) -> None:
    """토론 엔진 실행 래퍼. 예외를 로깅하고 삼키지 않음."""
    try:
        await run_debate(match_id)
    except Exception:
        logger.exception("토론 엔진 오류 (match_id=%s)", match_id)


@router.post("/{topic_id}/join")
async def join_topic_queue(
    topic_id: str,
    data: JoinQueueRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토픽 큐 참가. 2명 도달 시 자동 매치 생성."""
    service = DebateMatchingService(db)
    try:
        result = await service.join_queue(user, topic_id, data.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 매치가 생성되었으면 BackgroundTasks로 토론 엔진 시작 (참조 유지 + 예외 로깅)
    if result.get("status") == "matched" and result.get("match_id"):
        background_tasks.add_task(_run_debate_safe, result["match_id"])

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

    # 큐 등록 여부 확인
    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    in_queue = queue_result.scalar_one_or_none() is not None

    if not in_queue:
        # SSE 연결 전 이미 매칭된 경우 → 즉시 matched 이벤트 반환
        # (2번째 플레이어가 큐에서 제거된 직후 대기방에 도달하는 레이스 컨디션 처리)
        match_result = await db.execute(
            select(DebateMatch)
            .where(
                DebateMatch.topic_id == topic_id,
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id),
            )
            .order_by(DebateMatch.created_at.desc())
            .limit(1)
        )
        match = match_result.scalar_one_or_none()
        if match is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent not in queue")

        opponent_id = str(match.agent_b_id) if str(match.agent_a_id) == agent_id else str(match.agent_a_id)
        payload = json.dumps(
            {
                "event": "matched",
                "data": {"match_id": str(match.id), "opponent_agent_id": opponent_id, "auto_matched": False},
            },
            ensure_ascii=False,
        )

        async def _immediate_matched():
            yield f"data: {payload}\n\n"

        return StreamingResponse(
            _immediate_matched(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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
        # DB에서 직접 COUNT로 대기 위치 계산 (전체 로드 방지)
        pos_result = await db.execute(
            select(func.count(DebateMatchQueue.id)).where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.joined_at <= entry.joined_at,
            )
        )
        position = pos_result.scalar() or 1
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
        opponent_id = str(match.agent_b_id) if str(match.agent_a_id) == agent_id else str(match.agent_a_id)
        return {"status": "matched", "match_id": str(match.id), "opponent_agent_id": opponent_id}

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


def _topic_response(topic, queue_count: int = 0, match_count: int = 0) -> dict:
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
        "queue_count": queue_count,
        "match_count": match_count,
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
        "created_by": str(topic.created_by) if topic.created_by else None,
        "creator_nickname": topic.creator_nickname if hasattr(topic, "creator_nickname") else None,
    }
