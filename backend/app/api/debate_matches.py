from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.debate_match import PredictionCreate, TurnLogResponse
from app.services.debate_broadcast import subscribe
from app.services.debate_match_service import DebateMatchService

router = APIRouter()


@router.get("/featured")
async def get_featured_matches(
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """하이라이트 매치 목록."""
    service = DebateMatchService(db)
    items, total = await service.list_featured(limit=limit)
    return {"items": items, "total": total}


@router.get("/{match_id}/viewers")
async def get_viewer_count(
    match_id: str,
    user: User = Depends(get_current_user),
):
    """현재 관전자 수 조회. Redis Set debate:viewers:{match_id}"""
    from app.core.redis import redis_client

    count = await redis_client.scard(f"debate:viewers:{match_id}")
    return {"count": count}


@router.post("/{match_id}/predictions", status_code=status.HTTP_201_CREATED)
async def create_prediction(
    match_id: str,
    data: PredictionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """예측 투표. in_progress 매치 && turn_count<=2만 허용."""
    service = DebateMatchService(db)
    try:
        return await service.create_prediction(match_id, user.id, data.prediction)
    except ValueError as exc:
        detail = str(exc)
        if "DUPLICATE" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 투표했습니다") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get("/{match_id}/predictions")
async def get_predictions(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """예측 투표 통계 및 내 투표 결과 조회."""
    service = DebateMatchService(db)
    return await service.get_prediction_stats(match_id, user.id)


@router.get("/{match_id}/summary")
async def get_match_summary(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토론 요약 리포트 조회. 생성 중이면 generating, 완료면 ready."""
    from sqlalchemy import select

    from app.models.debate_match import DebateMatch

    res = await db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
    match = res.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if match.status != "completed":
        return {"status": "unavailable"}
    if match.summary_report is None:
        return {"status": "generating"}
    return {"status": "ready", **match.summary_report}


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
