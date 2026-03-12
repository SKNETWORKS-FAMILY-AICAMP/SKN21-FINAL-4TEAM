"""OpenAI provider 구현."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# max_tokens 대신 max_completion_tokens를 사용해야 하는 모델 접두사
# o-series 추론 모델(o1/o3/o4)과 gpt-4.1+/gpt-5+ 계열은 max_completion_tokens 필수
_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "o4", "gpt-4.1", "gpt-5")

# temperature 파라미터를 지원하지 않는 모델 접두사 (o-series 추론 모델 + gpt-5 계열)
_NO_TEMPERATURE_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def openai_max_tokens_key(model_id: str) -> str:
    """모델에 따라 max_tokens 또는 max_completion_tokens 파라미터 키를 반환."""
    model = model_id.lower()
    if any(model.startswith(p) for p in _COMPLETION_TOKENS_PREFIXES):
        return "max_completion_tokens"
    return "max_tokens"


def openai_supports_temperature(model_id: str) -> bool:
    """모델이 temperature 파라미터를 지원하는지 반환. o-series 추론 모델과 gpt-5 계열만 미지원."""
    model = model_id.lower()
    return not any(model.startswith(p) for p in _NO_TEMPERATURE_PREFIXES)


class OpenAIProvider(BaseProvider):
    """OpenAI API provider.

    HTTP 클라이언트는 외부에서 주입받아 InferenceClient의 커넥션 풀을 공유한다.
    """

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        # None이면 generate/stream 호출 시 InferenceClient._http를 통해 주입받음
        # 단독 인스턴스화 시에는 임시 클라이언트를 생성
        self._http = http

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            # 단독 사용 시 폴백 — 실제 운영에서는 InferenceClient가 주입
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        return await self._call_impl(model_id, settings.openai_api_key, messages, **kwargs)

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        return await self._call_impl(model_id, api_key, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._stream_impl(model_id, settings.openai_api_key, messages, usage_out, **kwargs):
            yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._stream_impl(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _call_impl(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """OpenAI chat completions 호출 구현 (플랫폼/BYOK 공통)."""
        max_key = openai_max_tokens_key(model_id)
        body: dict = {
            "model": model_id,
            "messages": messages,
            max_key: kwargs.get("max_tokens", 1024),
        }
        # o-series 추론 모델만 temperature 미지원, gpt-4.1/gpt-5 등은 temperature 지원
        if openai_supports_temperature(model_id):
            body["temperature"] = kwargs.get("temperature", 0.7)
        if "response_format" in kwargs:
            body["response_format"] = kwargs["response_format"]
        response = await self._get_http().post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        return {
            "content": choice["message"]["content"],
            "input_tokens": data["usage"]["prompt_tokens"],
            "output_tokens": data["usage"]["completion_tokens"],
            "finish_reason": choice["finish_reason"],
        }

    async def _stream_impl(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """OpenAI SSE 스트리밍 구현 (플랫폼/BYOK 공통). stream_options로 usage 포함."""
        max_key = openai_max_tokens_key(model_id)
        body: dict = {
            "model": model_id,
            "messages": messages,
            max_key: kwargs.get("max_tokens", 1024),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if openai_supports_temperature(model_id):
            body["temperature"] = kwargs.get("temperature", 0.7)
        async with self._get_http().stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        ) as response:
            response.raise_for_status()
            async for chunk in _iter_openai_sse(response, usage_out):
                yield chunk


async def _iter_openai_sse(
    response: httpx.Response, usage_out: dict
) -> AsyncGenerator[str, None]:
    """OpenAI-compatible SSE 스트림 파서. OpenAI/RunPod 공통 사용."""
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        chunk = json.loads(payload)
        if chunk.get("usage"):
            usage_out["input_tokens"] = chunk["usage"].get("prompt_tokens", 0)
            usage_out["output_tokens"] = chunk["usage"].get("completion_tokens", 0)
        choices = chunk.get("choices") or []
        if choices:
            finish_reason = choices[0].get("finish_reason")
            if finish_reason:
                usage_out["finish_reason"] = finish_reason
            delta = choices[0].get("delta", {})
            if "content" in delta:
                yield delta["content"]
