from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.debate_match import MatchListResponse, TurnLogResponse
from app.services.debate_broadcast import subscribe
from app.services.debate_match_service import DebateMatchService

router = APIRouter()


@router.get("/{match_id}")
async def get_match(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매치 상세 조회."""
    service = DebateMatchService(db)
    match = await service.get_match(match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return match


@router.get("/{match_id}/turns", response_model=list[TurnLogResponse])
async def get_match_turns(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매치 턴 로그 조회."""
    service = DebateMatchService(db)
    turns = await service.get_match_turns(match_id)
    return [TurnLogResponse.model_validate(t) for t in turns]


@router.get("/{match_id}/scorecard")
async def get_scorecard(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """스코어카드 조회."""
    service = DebateMatchService(db)
    scorecard = await service.get_scorecard(match_id)
    if scorecard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scorecard not available")
    return scorecard


@router.get("/{match_id}/stream")
async def stream_match(
    match_id: str,
    user: User = Depends(get_current_user),
):
    """매치 라이브 SSE 스트림."""
    return StreamingResponse(
        subscribe(match_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("")
async def list_matches(
    topic_id: str | None = None,
    agent_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateMatchService(db)
    items, total = await service.list_matches(
        topic_id=topic_id, agent_id=agent_id, status=status_filter, skip=skip, limit=limit
    )
    return {"items": items, "total": total}
