"""RunPod Serverless (SGLang) provider 구현.

RunPod SGLang은 OpenAI-compatible API를 제공하므로
OpenAI SSE 파서를 재사용한다.
"""

import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import BaseProvider
from app.services.llm.providers.openai_provider import _iter_openai_sse

logger = logging.getLogger(__name__)

_RUNPOD_BASE_URL = "https://api.runpod.ai/v2/{endpoint_id}/openai/v1"


class RunPodProvider(BaseProvider):
    """RunPod Serverless SGLang provider. OpenAI-compatible 엔드포인트 사용."""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    def _base_url(self) -> str:
        return _RUNPOD_BASE_URL.format(endpoint_id=settings.runpod_endpoint_id)

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        response = await self._get_http().post(
            f"{self._base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.runpod_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            },
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return {
            "content": choice["message"]["content"],
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        # RunPod는 엔드포인트 ID가 플랫폼 수준에서 고정되므로 BYOK는 플랫폼 호출과 동일
        # api_key를 사용자 키로 교체하는 시나리오가 없어 generate()로 위임
        return await self.generate(model_id, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async with self._get_http().stream(
            "POST",
            f"{self._base_url()}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.runpod_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
                "stream": True,
                "stream_options": {"include_usage": True},
            },
        ) as response:
            response.raise_for_status()
            async for chunk in _iter_openai_sse(response, usage_out):
                yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        # RunPod는 BYOK 스트리밍도 플랫폼 키로 처리
        async for chunk in self.stream(model_id, messages, usage_out, **kwargs):
            yield chunk
