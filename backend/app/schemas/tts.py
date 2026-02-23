from pydantic import BaseModel, Field


class TTSSynthesizeRequest(BaseModel):
    """TTS 합성 요청."""

    text: str = Field(..., min_length=1, max_length=4000)
    voice: str | None = None  # None이면 설정 기본값 사용
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class TTSMessageRequest(BaseModel):
    """채팅 메시지 기반 TTS 요청."""

    message_id: int
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class TTSSynthesizeResponse(BaseModel):
    """TTS 합성 결과."""

    audio_url: str
    duration_seconds: float | None = None
    characters_count: int
    provider: str
    voice: str


class TTSVoice(BaseModel):
    """사용 가능한 TTS 음성."""

    voice_id: str
    name: str
    language: str | None = None
    preview_url: str | None = None


class TTSVoiceListResponse(BaseModel):
    """TTS 음성 목록."""

    voices: list[TTSVoice]
    provider: str
