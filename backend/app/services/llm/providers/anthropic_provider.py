"""Anthropic provider 구현."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Messages API provider."""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        return await self._call_impl(model_id, settings.anthropic_api_key, messages, **kwargs)

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        return await self._call_impl(model_id, api_key, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._stream_impl(model_id, settings.anthropic_api_key, messages, usage_out, **kwargs):
            yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._stream_impl(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _call_impl(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """Anthropic Messages API 호출 구현 (플랫폼/BYOK 공통)."""
        system_prompt, api_messages = self._split_system_messages(messages)
        body: dict = {
            "model": model_id,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
        }
        if system_prompt:
            body["system"] = system_prompt
        response = await self._get_http().post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        content_text = "".join(block["text"] for block in data["content"] if block["type"] == "text")
        return {
            "content": content_text,
            "input_tokens": data["usage"]["input_tokens"],
            "output_tokens": data["usage"]["output_tokens"],
            "finish_reason": data.get("stop_reason", "end_turn"),
        }

    async def _stream_impl(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Anthropic Messages API SSE 스트리밍 구현 (플랫폼/BYOK 공통).

        message_start/message_delta에서 usage 캡처.
        """
        system_prompt, api_messages = self._split_system_messages(messages)
        body: dict = {
            "model": model_id,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": True,
        }
        if system_prompt:
            body["system"] = system_prompt
        async with self._get_http().stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        ) as response:
            response.raise_for_status()
            async for chunk in _iter_anthropic_sse(response, usage_out):
                yield chunk

    @staticmethod
    def _split_system_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages에서 system 메시지를 분리.

        Anthropic API는 system을 별도 파라미터로 전달해야 하므로
        system 역할 메시지를 하나의 문자열로 합치고 나머지를 반환.
        """
        system_parts = []
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        return "\n\n".join(system_parts), api_messages


async def _iter_anthropic_sse(
    response: httpx.Response, usage_out: dict
) -> AsyncGenerator[str, None]:
    """Anthropic Messages API SSE 파서. message_start/delta에서 usage 캡처."""
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "message_start":
            usage_out["input_tokens"] = event.get("message", {}).get("usage", {}).get("input_tokens", 0)
        elif event_type == "message_delta":
            usage_out["output_tokens"] = event.get("usage", {}).get("output_tokens", 0)
            # Anthropic: max_tokens → OpenAI 규격 "length"로 정규화
            stop_reason = event.get("delta", {}).get("stop_reason")
            if stop_reason:
                usage_out["finish_reason"] = "length" if stop_reason == "max_tokens" else stop_reason
        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                yield delta["text"]
        elif event_type == "message_stop":
            break
