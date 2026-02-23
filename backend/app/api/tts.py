"""TTS API 엔드포인트.

사용자가 텍스트 또는 채팅 메시지를 음성으로 합성할 수 있다.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from app.schemas.tts import (
    TTSMessageRequest,
    TTSSynthesizeRequest,
    TTSSynthesizeResponse,
    TTSVoiceListResponse,
)
from app.services.tts_service import TTSService

router = APIRouter()


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def synthesize_text(
    data: TTSSynthesizeRequest,
    user: User = Depends(get_current_user),
):
    """텍스트를 음성으로 합성."""
    svc = TTSService()
    result = await svc.synthesize(text=data.text, voice=data.voice, speed=data.speed)
    return result


@router.post("/synthesize-message", response_model=TTSSynthesizeResponse)
async def synthesize_message(
    data: TTSMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """채팅 메시지를 음성으로 합성. 본인 세션의 메시지만 허용."""
    # 메시지 조회
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == data.message_id))
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # 세션 소유자 확인
    session_result = await db.execute(select(ChatSession).where(ChatSession.id == message.session_id))
    session = session_result.scalar_one_or_none()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")

    svc = TTSService()
    result = await svc.synthesize(text=message.content, voice=data.voice, speed=data.speed)
    return result


@router.get("/voices", response_model=TTSVoiceListResponse)
async def list_voices(
    user: User = Depends(get_current_user),
):
    """사용 가능한 TTS 음성 목록."""
    svc = TTSService()
    return await svc.list_voices()
