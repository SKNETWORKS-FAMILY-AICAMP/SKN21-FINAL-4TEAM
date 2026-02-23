"""AI 이미지 생성 서비스.

멀티 프로바이더 지원: OpenAI DALL-E 3, Stability AI.
생성된 이미지를 로컬에 저장하고 URL을 반환한다.
"""

import base64
import logging
import os
import uuid

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_IMAGE_DIR = "images/generated"

# 스타일 프롬프트 접두사 — 사용자 프롬프트 앞에 붙여 스타일 유도
_STYLE_PREFIXES = {
    "anime": "anime style illustration, ",
    "realistic": "photorealistic, high detail, ",
    "cartoon": "cartoon style, vibrant colors, ",
    "oil_painting": "oil painting style, textured brushstrokes, ",
    "watercolor": "watercolor painting, soft edges, ",
    "pixel": "pixel art style, retro, ",
}

_OPENAI_STYLES = list(_STYLE_PREFIXES.keys())
_STABILITY_STYLES = list(_STYLE_PREFIXES.keys())


class ImageGenService:
    """AI 이미지 생성 서비스. OpenAI DALL-E 3 / Stability AI 지원."""

    def __init__(self) -> None:
        self._image_dir = os.path.join(settings.upload_dir, _IMAGE_DIR)
        os.makedirs(self._image_dir, exist_ok=True)

    async def generate(
        self,
        prompt: str,
        style: str | None = None,
        width: int = 1024,
        height: int = 1024,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> dict:
        """프롬프트로 이미지를 생성하여 로컬에 저장, URL 반환."""
        if not settings.image_gen_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image generation is disabled",
            )

        provider = settings.image_gen_provider
        style = style or settings.image_gen_default_style

        # 스타일 접두사 적용
        styled_prompt = _STYLE_PREFIXES.get(style, "") + prompt

        match provider:
            case "openai":
                image_bytes = await self._generate_openai(styled_prompt, width, height)
            case "stability":
                image_bytes = await self._generate_stability(
                    styled_prompt, width, height, negative_prompt, seed
                )
            case _:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported image generation provider: {provider}",
                )

        filename = f"{uuid.uuid4().hex}.png"
        filepath = os.path.join(self._image_dir, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        logger.info("Image generated: %s (%d bytes, provider=%s)", filename, len(image_bytes), provider)

        return {
            "image_url": f"/uploads/{_IMAGE_DIR}/{filename}",
            "prompt": prompt,
            "style": style,
            "width": width,
            "height": height,
            "seed": seed,
            "provider": provider,
        }

    async def list_styles(self) -> dict:
        """사용 가능한 이미지 스타일 목록 반환."""
        provider = settings.image_gen_provider
        match provider:
            case "openai":
                styles = _OPENAI_STYLES
            case "stability":
                styles = _STABILITY_STYLES
            case _:
                styles = []
        return {"styles": styles, "provider": provider}

    # ── OpenAI DALL-E 3 ──

    async def _generate_openai(self, prompt: str, width: int, height: int) -> bytes:
        """OpenAI DALL-E 3 API로 이미지 생성."""
        api_key = settings.openai_api_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI API key not configured for image generation",
            )

        # DALL-E 3는 1024x1024, 1792x1024, 1024x1792만 지원
        size = self._normalize_dalle_size(width, height)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "response_format": "b64_json",
                    "quality": "standard",
                },
            )
            if response.status_code != 200:
                logger.error("OpenAI DALL-E error %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Image generation failed",
                )

            data = response.json()
            b64_data = data["data"][0]["b64_json"]
            return base64.b64decode(b64_data)

    @staticmethod
    def _normalize_dalle_size(width: int, height: int) -> str:
        """DALL-E 3 지원 사이즈로 정규화."""
        if width > height:
            return "1792x1024"
        elif height > width:
            return "1024x1792"
        return "1024x1024"

    # ── Stability AI ──

    async def _generate_stability(
        self, prompt: str, width: int, height: int, negative_prompt: str | None, seed: int | None
    ) -> bytes:
        """Stability AI API로 이미지 생성."""
        api_key = settings.stability_api_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stability AI API key not configured",
            )

        # 64의 배수로 정규화
        width = (width // 64) * 64
        height = (height // 64) * 64

        payload: dict = {
            "prompt": prompt,
            "output_format": "png",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.stability.ai/v2beta/stable-image/generate/sd3",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "image/*",
                },
                files={"none": ("", b"")},
                data=payload,
            )
            if response.status_code != 200:
                logger.error("Stability AI error %d: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Image generation failed",
                )
            return response.content
