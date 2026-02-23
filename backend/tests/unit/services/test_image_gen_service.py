"""이미지 생성 서비스 단위 테스트."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.image_gen_service import ImageGenService


@pytest.fixture
def image_gen_service(tmp_path):
    """임시 디렉토리를 upload_dir로 사용하는 ImageGenService."""
    with patch("app.services.image_gen_service.settings") as mock_settings:
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.image_gen_enabled = True
        mock_settings.image_gen_provider = "openai"
        mock_settings.image_gen_default_style = "anime"
        mock_settings.openai_api_key = "test-key"
        mock_settings.stability_api_key = ""
        yield ImageGenService()


@pytest.mark.asyncio
async def test_generate_openai_success(image_gen_service):
    """OpenAI DALL-E 이미지 생성 성공."""
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    b64_image = base64.b64encode(fake_image).decode()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"b64_json": b64_image}]}

    with patch("app.services.image_gen_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await image_gen_service.generate("cute cat")

    assert result["image_url"].startswith("/uploads/images/generated/")
    assert result["image_url"].endswith(".png")
    assert result["prompt"] == "cute cat"
    assert result["style"] == "anime"
    assert result["provider"] == "openai"


@pytest.mark.asyncio
async def test_generate_custom_style(image_gen_service):
    """커스텀 스타일 지정."""
    fake_image = b"\x89PNG" + b"\x00" * 100
    b64_image = base64.b64encode(fake_image).decode()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"b64_json": b64_image}]}

    with patch("app.services.image_gen_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await image_gen_service.generate("landscape", style="watercolor")

    assert result["style"] == "watercolor"


@pytest.mark.asyncio
async def test_generate_openai_api_error(image_gen_service):
    """OpenAI API 에러 시 502 반환."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("app.services.image_gen_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await image_gen_service.generate("test")
        assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_generate_disabled():
    """이미지 생성 비활성화 시 503 반환."""
    with patch("app.services.image_gen_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.image_gen_enabled = False
        svc = ImageGenService()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.generate("test")
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_generate_no_api_key():
    """API 키 미설정 시 503 반환."""
    with patch("app.services.image_gen_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.image_gen_enabled = True
        mock_settings.image_gen_provider = "openai"
        mock_settings.image_gen_default_style = "anime"
        mock_settings.openai_api_key = ""
        svc = ImageGenService()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.generate("test")
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_list_styles_openai(image_gen_service):
    """OpenAI 스타일 목록 반환."""
    result = await image_gen_service.list_styles()

    assert result["provider"] == "openai"
    assert "anime" in result["styles"]
    assert "realistic" in result["styles"]
    assert len(result["styles"]) >= 5


@pytest.mark.asyncio
async def test_normalize_dalle_size():
    """DALL-E 사이즈 정규화."""
    assert ImageGenService._normalize_dalle_size(1024, 1024) == "1024x1024"
    assert ImageGenService._normalize_dalle_size(1920, 1080) == "1792x1024"
    assert ImageGenService._normalize_dalle_size(768, 1280) == "1024x1792"


@pytest.mark.asyncio
async def test_unsupported_provider():
    """지원하지 않는 provider 시 400 반환."""
    with patch("app.services.image_gen_service.settings") as mock_settings:
        mock_settings.upload_dir = "/tmp"
        mock_settings.image_gen_enabled = True
        mock_settings.image_gen_provider = "unknown"
        mock_settings.image_gen_default_style = "anime"
        svc = ImageGenService()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.generate("test")
        assert exc_info.value.status_code == 400
