"""캐릭터 간 1:1 대화 API."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.character_chat import (
    ChatDetailResponse,
    ChatMessageResponse,
    ChatParticipant,
    ChatRequestCreate,
    ChatRequestRespond,
    ChatSessionListResponse,
    ChatSessionResponse,
)
from app.services.character_chat_service import CharacterChatService

router = APIRouter()


def _build_session_response(session, req_persona=None, resp_persona=None) -> ChatSessionResponse:
    """세션 + 페르소나를 ChatSessionResponse로 변환."""
    return ChatSessionResponse(
        id=session.id,
        requester=ChatParticipant(
            persona_id=session.requester_persona_id,
            display_name=req_persona.display_name if req_persona else "Unknown",
            owner_id=session.requester_owner_id,
        ),
        responder=ChatParticipant(
            persona_id=session.responder_persona_id,
            display_name=resp_persona.display_name if resp_persona else "Unknown",
            owner_id=session.responder_owner_id,
        ),
        status=session.status,
        max_turns=session.max_turns,
        current_turn=session.current_turn,
        is_public=session.is_public,
        age_rating=session.age_rating,
        total_cost=float(session.total_cost),
        requested_at=session.requested_at,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


@router.post("/request", response_model=ChatSessionResponse)
async def request_chat(
    body: ChatRequestCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """1:1 캐릭터 채팅 요청."""
    svc = CharacterChatService(db)
    session = await svc.request_chat(
        requester_persona_id=body.requester_persona_id,
        responder_persona_id=body.responder_persona_id,
        user=user,
        max_turns=body.max_turns,
        is_public=body.is_public,
    )
    data = await svc.get_session(session.id, user)
    return _build_session_response(
        data["session"], data["requester_persona"], data["responder_persona"]
    )


@router.post("/{session_id}/respond", response_model=ChatSessionResponse)
async def respond_to_request(
    session_id: uuid.UUID,
    body: ChatRequestRespond,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """채팅 요청 수락/거절."""
    svc = CharacterChatService(db)
    session = await svc.respond_to_request(session_id, user, body.accept)
    data = await svc.get_session(session.id, user)
    return _build_session_response(
        data["session"], data["requester_persona"], data["responder_persona"]
    )


@router.get("/{session_id}", response_model=ChatDetailResponse)
async def get_chat_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대화 내용 조회."""
    svc = CharacterChatService(db)
    data = await svc.get_session(session_id, user)
    session_resp = _build_session_response(
        data["session"], data["requester_persona"], data["responder_persona"]
    )
    messages = [
        ChatMessageResponse(
            id=m.id,
            persona_id=m.persona_id,
            persona_display_name=(
                data["requester_persona"].display_name
                if m.persona_id == data["session"].requester_persona_id
                else data["responder_persona"].display_name
            ),
            content=m.content,
            turn_number=m.turn_number,
            created_at=m.created_at,
        )
        for m in data["messages"]
    ]
    return ChatDetailResponse(session=session_resp, messages=messages)


@router.post("/{session_id}/advance", response_model=ChatMessageResponse)
async def advance_chat(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """다음 턴 생성."""
    svc = CharacterChatService(db)
    msg = await svc.advance_chat(session_id, user)
    persona = await svc._get_persona(msg.persona_id)
    return ChatMessageResponse(
        id=msg.id,
        persona_id=msg.persona_id,
        persona_display_name=persona.display_name if persona else "Unknown",
        content=msg.content,
        turn_number=msg.turn_number,
        created_at=msg.created_at,
    )


@router.get("/requests/incoming", response_model=ChatSessionListResponse)
async def list_incoming_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """수신 채팅 요청 목록."""
    svc = CharacterChatService(db)
    data = await svc.list_requests(user, direction="incoming", skip=skip, limit=limit)
    # 간단 변환 (페르소나 이름 없이)
    items = [
        ChatSessionResponse(
            id=s.id,
            requester=ChatParticipant(
                persona_id=s.requester_persona_id, display_name="", owner_id=s.requester_owner_id
            ),
            responder=ChatParticipant(
                persona_id=s.responder_persona_id, display_name="", owner_id=s.responder_owner_id
            ),
            status=s.status,
            max_turns=s.max_turns,
            current_turn=s.current_turn,
            is_public=s.is_public,
            age_rating=s.age_rating,
            total_cost=float(s.total_cost),
            requested_at=s.requested_at,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in data["items"]
    ]
    return ChatSessionListResponse(items=items, total=data["total"])


@router.get("/requests/outgoing", response_model=ChatSessionListResponse)
async def list_outgoing_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """발신 채팅 요청 목록."""
    svc = CharacterChatService(db)
    data = await svc.list_requests(user, direction="outgoing", skip=skip, limit=limit)
    items = [
        ChatSessionResponse(
            id=s.id,
            requester=ChatParticipant(
                persona_id=s.requester_persona_id, display_name="", owner_id=s.requester_owner_id
            ),
            responder=ChatParticipant(
                persona_id=s.responder_persona_id, display_name="", owner_id=s.responder_owner_id
            ),
            status=s.status,
            max_turns=s.max_turns,
            current_turn=s.current_turn,
            is_public=s.is_public,
            age_rating=s.age_rating,
            total_cost=float(s.total_cost),
            requested_at=s.requested_at,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in data["items"]
    ]
    return ChatSessionListResponse(items=items, total=data["total"])
