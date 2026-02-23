"""TTS 합성 서비스.

멀티 프로바이더 지원: OpenAI TTS, ElevenLabs, Google Cloud TTS.
합성된 오디오를 로컬에 저장하고 URL을 반환한다.
"""

import logging
import os
import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI TTS 기본 음성 목록
_OPENAI_VOICES = [
    {"voice_id": "alloy", "name": "Alloy", "language": "multilingual"},
    {"voice_id": "echo", "name": "Echo", "language": "multilingual"},
    {"voice_id": "fable", "name": "Fable", "language": "multilingual"},
    {"voice_id": "onyx", "name": "Onyx", "language": "multilingual"},
    {"voice_id": "nova", "name": "Nova", "language": "multilingual"},
    {"voice_id": "shimmer", "name": "Shimmer", "language": "multilingual"},
]

# ElevenLabs 기본 음성 (API 호출로 동적 조회도 가능)
_ELEVENLABS_DEFAULT_VOICES = [
    {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "language": "multilingual"},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "language": "multilingual"},
    {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "language": "multilingual"},
]

_AUDIO_DIR = "audio"
_FORMAT_EXTENSIONS = {"mp3": "mp3", "opus": "opus", "aac": "aac", "wav": "wav"}


class TTSService:
    """TTS 합성 서비스. OpenAI TTS / ElevenLabs 지원."""

    def __init__(self) -> None:
        self._audio_dir = os.path.join(settings.upload_dir, _AUDIO_DIR)
        os.makedirs(self._audio_dir, exist_ok=True)

    async def synthesize(self, text: str, voice: str | None = None, speed: float = 1.0) -> dict:
        """텍스트를 음성으로 합성하여 로컬에 저장, URL 반환."""
        if not settings.tts_enabled:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS is disabled")

        provider = settings.tts_provider
        voice = voice or settings.tts_default_voice

        match provider:
            case "openai":
                audio_bytes = await self._synthesize_openai(text, voice, speed)
            case "elevenlabs":
                audio_bytes = await self._synthesize_elevenlabs(text, voice)
            case _:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported TTS provider: {provider}",
                )

        ext = _FORMAT_EXTENSIONS.get(settings.tts_output_format, "mp3")
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(self._audio_dir, filename)

        Path(filepath).write_bytes(audio_bytes)
        logger.info("TTS audio saved: %s (%d bytes, provider=%s)", filename, len(audio_bytes), provider)

        return {
            "audio_url": f"/uploads/{_AUDIO_DIR}/{filename}",
            "duration_seconds": None,
            "characters_count": len(text),
            "provider": provider,
            "voice": voice,
        }

    async def list_voices(self) -> dict:
        """사용 가능한 TTS 음성 목록 반환."""
        provider = settings.tts_provider

        match provider:
            case "openai":
                voices = _OPENAI_VOICES
            case "elevenlabs":
                voices = await self._list_elevenlabs_voices()
            case _:
                voices = []

        return {"voices": voices, "provider": provider}

    # ── OpenAI TTS ──

    async def _synthesize_openai(self, text: str, voice: str, speed: float) -> bytes:
        """OpenAI TTS API로 음성 합성."""
        api_key = settings.openai_api_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI API key not configured for TTS",
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": voice,
                    "response_format": settings.tts_output_format,
                    "speed": speed,
                },
            )
            if response.status_code != 200:
                logger.error("OpenAI TTS error %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="TTS synthesis failed",
                )
            return response.content

    # ── ElevenLabs ──

    async def _synthesize_elevenlabs(self, text: str, voice_id: str) -> bytes:
        """ElevenLabs API로 음성 합성."""
        api_key = settings.elevenlabs_api_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ElevenLabs API key not configured",
            )

        voice_id = voice_id or settings.elevenlabs_default_voice_id
        if not voice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No voice_id specified for ElevenLabs",
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
            )
            if response.status_code != 200:
                logger.error("ElevenLabs TTS error %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="TTS synthesis failed",
                )
            return response.content

    async def _list_elevenlabs_voices(self) -> list[dict]:
        """ElevenLabs API에서 사용 가능한 음성 목록 조회."""
        api_key = settings.elevenlabs_api_key
        if not api_key:
            return _ELEVENLABS_DEFAULT_VOICES

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": api_key},
                )
                response.raise_for_status()
                data = response.json()
                return [
                    {
                        "voice_id": v["voice_id"],
                        "name": v.get("name", "Unknown"),
                        "language": v.get("labels", {}).get("language"),
                        "preview_url": v.get("preview_url"),
                    }
                    for v in data.get("voices", [])
                ]
        except Exception:
            logger.warning("Failed to fetch ElevenLabs voices, using defaults")
            return _ELEVENLABS_DEFAULT_VOICES
