import json
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.chat import MessageCreate, MessageResponse, SessionCreate, SessionResponse
from app.services.chat_service import ChatService

router = APIRouter()


class SessionListResponse:
    """인라인 응답 모델 (Pydantic 미사용 — dict 반환)."""
    pass


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 채팅 세션 생성."""
    service = ChatService(db)
    return await service.create_session(
        user=user,
        persona_id=data.persona_id,
        webtoon_id=data.webtoon_id,
        llm_model_id=data.llm_model_id,
    )


@router.get("/sessions")
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 채팅 세션 목록."""
    service = ChatService(db)
    result = await service.get_user_sessions(user, skip=skip, limit=limit)
    return {
        "items": [SessionResponse.model_validate(s) for s in result["items"]],
        "total": result["total"],
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 메시지 히스토리 조회."""
    service = ChatService(db)
    result = await service.get_session_messages(session_id, user, skip=skip, limit=limit)
    return {
        "items": [MessageResponse.model_validate(m) for m in result["items"]],
        "total": result["total"],
    }


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: uuid.UUID,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """메시지 전송 → LLM 응답 (비스트리밍)."""
    service = ChatService(db)
    return await service.send_message(session_id, user, data.content)


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: uuid.UUID,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """메시지 전송 → SSE 스트리밍 응답."""
    service = ChatService(db)

    async def event_generator():
        async for chunk in service.send_message_stream(session_id, user, data.content):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
