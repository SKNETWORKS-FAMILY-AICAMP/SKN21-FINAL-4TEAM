"""TTS 서비스 단위 테스트."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.tts_service import TTSService


@pytest.fixture
def tts_service(tmp_path):
    """임시 디렉토리를 upload_dir로 사용하는 TTSService."""
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.tts_enabled = True
        mock_settings.tts_provider = "openai"
        mock_settings.tts_default_voice = "alloy"
        mock_settings.tts_output_format = "mp3"
        mock_settings.openai_api_key = "test-key"
        mock_settings.elevenlabs_api_key = ""
        mock_settings.elevenlabs_default_voice_id = ""
        yield TTSService()


@pytest.mark.asyncio
async def test_synthesize_openai_success(tts_service):
    """OpenAI TTS 합성 성공."""
    fake_audio = b"\xff\xfb\x90\x00" * 100  # 가짜 MP3 바이트

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_audio

    with patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await tts_service.synthesize("안녕하세요")

    assert result["audio_url"].startswith("/uploads/audio/")
    assert result["audio_url"].endswith(".mp3")
    assert result["characters_count"] == 5
    assert result["provider"] == "openai"
    assert result["voice"] == "alloy"


@pytest.mark.asyncio
async def test_synthesize_custom_voice(tts_service):
    """커스텀 음성 지정 시 해당 음성 사용."""
    fake_audio = b"\xff\xfb\x90\x00" * 100

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_audio

    with patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await tts_service.synthesize("테스트", voice="nova")

    assert result["voice"] == "nova"


@pytest.mark.asyncio
async def test_synthesize_openai_api_error(tts_service):
    """OpenAI API 에러 시 502 반환."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await tts_service.synthesize("에러 테스트")
        assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_synthesize_disabled():
    """TTS 비활성화 시 503 반환."""
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.tts_enabled = False
        svc = TTSService()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.synthesize("테스트")
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_synthesize_no_api_key():
    """API 키 미설정 시 503 반환."""
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.tts_enabled = True
        mock_settings.tts_provider = "openai"
        mock_settings.tts_default_voice = "alloy"
        mock_settings.openai_api_key = ""
        svc = TTSService()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.synthesize("테스트")
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_list_voices_openai(tts_service):
    """OpenAI 음성 목록 반환."""
    result = await tts_service.list_voices()

    assert result["provider"] == "openai"
    assert len(result["voices"]) == 6
    voice_ids = [v["voice_id"] for v in result["voices"]]
    assert "alloy" in voice_ids
    assert "nova" in voice_ids


@pytest.mark.asyncio
async def test_list_voices_elevenlabs_with_api():
    """ElevenLabs API 키 있을 때 API에서 음성 목록 조회."""
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.tts_enabled = True
        mock_settings.tts_provider = "elevenlabs"
        mock_settings.elevenlabs_api_key = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "voices": [
                {
                    "voice_id": "v1",
                    "name": "Test Voice",
                    "labels": {"language": "ko"},
                    "preview_url": "https://example.com/preview.mp3",
                }
            ]
        }

        with patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            svc = TTSService()
            result = await svc.list_voices()

        assert result["provider"] == "elevenlabs"
        assert len(result["voices"]) == 1
        assert result["voices"][0]["voice_id"] == "v1"


@pytest.mark.asyncio
async def test_unsupported_provider():
    """지원하지 않는 provider 시 400 반환."""
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.tts_enabled = True
        mock_settings.tts_provider = "unknown"
        mock_settings.tts_default_voice = "default"

        svc = TTSService()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.synthesize("테스트")
        assert exc_info.value.status_code == 400
