import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.chat_session import ChatSession
from app.models.live2d_model import Live2DModel
from app.models.persona import Persona
from app.models.user import User
from app.schemas.chat import (
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
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
        user_persona_id=data.user_persona_id,
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


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 상세 정보 (Live2D 모델 경로 & 감정 매핑 포함)."""
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # 페르소나 & Live2D 모델 로드
    persona_result = await db.execute(select(Persona).where(Persona.id == session.persona_id))
    persona = persona_result.scalar_one_or_none()

    # 성인인증 철회 후 18+ 세션 접근 차단
    if persona and persona.age_rating == "18+" and user.adult_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adult verification required",
            headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
        )

    live2d_model = None
    if persona and persona.live2d_model_id:
        live2d_result = await db.execute(select(Live2DModel).where(Live2DModel.id == persona.live2d_model_id))
        live2d_model = live2d_result.scalar_one_or_none()

    return {
        **SessionResponse.model_validate(session).model_dump(),
        "live2d_model_path": live2d_model.model_path if live2d_model else None,
        "live2d_emotion_mappings": live2d_model.emotion_mappings if live2d_model else None,
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
        try:
            async for chunk in service.send_message_stream(session_id, user, data.content):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except HTTPException as e:
            logger.error("SSE stream HTTPException: status=%s detail=%s", e.status_code, e.detail)
            yield f"data: {json.dumps({'error': e.detail, 'status': e.status_code})}\n\n"
        except Exception as e:
            logger.error("SSE stream error: %s", e, exc_info=True)
            error_msg = str(e) if settings.debug else "Internal server error"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 수정 (제목, 핀, 모델)."""
    service = ChatService(db)
    return await service.update_session(
        session_id,
        user,
        title=data.title,
        is_pinned=data.is_pinned,
        llm_model_id=data.llm_model_id,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 삭제 (소프트 삭제)."""
    service = ChatService(db)
    await service.delete_session(session_id, user)


@router.post("/sessions/{session_id}/archive", response_model=SessionResponse)
async def archive_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 아카이브."""
    service = ChatService(db)
    return await service.archive_session(session_id, user)


@router.post("/sessions/{session_id}/messages/{message_id}/regenerate")
async def regenerate_message(
    session_id: uuid.UUID,
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """assistant 메시지 재생성 (SSE 스트리밍)."""
    service = ChatService(db)

    async def event_generator():
        try:
            async for chunk in service.regenerate_message(session_id, message_id, user):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except HTTPException as e:
            logger.error("SSE regenerate HTTPException: status=%s detail=%s", e.status_code, e.detail)
            yield f"data: {json.dumps({'error': e.detail, 'status': e.status_code})}\n\n"
        except Exception as e:
            logger.error("SSE regenerate error: %s", e, exc_info=True)
            error_msg = str(e) if settings.debug else "Internal server error"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/sessions/{session_id}/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    session_id: uuid.UUID,
    message_id: int,
    data: MessageUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 메시지 수정."""
    service = ChatService(db)
    return await service.edit_message(session_id, message_id, user, data.content)


@router.get("/sessions/{session_id}/messages/{message_id}/siblings")
async def get_siblings(
    session_id: uuid.UUID,
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """형제 메시지 목록 (브랜칭 탐색)."""
    service = ChatService(db)
    result = await service.get_siblings(session_id, message_id, user)
    return {
        "messages": [MessageResponse.model_validate(m) for m in result["messages"]],
        "current_index": result["current_index"],
        "total": result["total"],
    }


@router.post("/sessions/{session_id}/messages/{message_id}/activate", response_model=MessageResponse)
async def activate_sibling(
    session_id: uuid.UUID,
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 형제 메시지 활성화."""
    service = ChatService(db)
    return await service.switch_sibling(session_id, message_id, user)
