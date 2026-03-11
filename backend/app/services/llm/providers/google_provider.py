"""Google Gemini provider 구현."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.llm.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    """Google Gemini API provider.

    API 키를 URL 파라미터 대신 헤더로 전달 — 로그/트레이스에 키 노출 방지.
    """

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        return await self._call_impl(model_id, settings.google_api_key, messages, **kwargs)

    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        return await self._call_impl(model_id, api_key, messages, **kwargs)

    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._stream_impl(model_id, settings.google_api_key, messages, usage_out, **kwargs):
            yield chunk

    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._stream_impl(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _call_impl(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """Google Gemini API 호출 구현 (플랫폼/BYOK 공통)."""
        system_prompt, gemini_contents = self._to_gemini_format(messages)
        body: dict = {
            "contents": gemini_contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        response = await self._get_http().post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        candidate = data["candidates"][0]
        content_text = "".join(part["text"] for part in candidate["content"]["parts"] if "text" in part)
        usage_meta = data.get("usageMetadata", {})
        return {
            "content": content_text,
            "input_tokens": usage_meta.get("promptTokenCount", 0),
            "output_tokens": usage_meta.get("candidatesTokenCount", 0),
            "finish_reason": candidate.get("finishReason", "STOP"),
        }

    async def _stream_impl(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Google Gemini API SSE 스트리밍 구현 (플랫폼/BYOK 공통).

        usageMetadata(마지막 청크)에서 토큰 수 캡처.
        """
        system_prompt, gemini_contents = self._to_gemini_format(messages)
        body: dict = {
            "contents": gemini_contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        async with self._get_http().stream(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent",
            params={"alt": "sse"},
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=body,
        ) as response:
            response.raise_for_status()
            async for chunk in _iter_google_sse(response, usage_out):
                yield chunk

    @staticmethod
    def _to_gemini_format(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages를 Gemini contents 형식으로 변환.

        Gemini는 role이 'user'와 'model'만 허용.
        system 메시지는 systemInstruction으로 분리.
        """
        system_parts = []
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
            else:
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        return "\n\n".join(system_parts), contents


async def _iter_google_sse(
    response: httpx.Response, usage_out: dict
) -> AsyncGenerator[str, None]:
    """Google Gemini SSE 파서. usageMetadata(마지막 청크)에서 토큰 수 캡처."""
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        try:
            chunk = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if chunk.get("usageMetadata"):
            meta = chunk["usageMetadata"]
            usage_out["input_tokens"] = meta.get("promptTokenCount", 0)
            usage_out["output_tokens"] = meta.get("candidatesTokenCount", 0)
        candidates = chunk.get("candidates", [])
        if not candidates:
            continue
        # Google: MAX_TOKENS → OpenAI 규격 "length"로 정규화
        finish_reason = candidates[0].get("finishReason", "")
        if finish_reason:
            usage_out["finish_reason"] = "length" if finish_reason == "MAX_TOKENS" else finish_reason.lower()
        for part in candidates[0].get("content", {}).get("parts", []):
            if "text" in part:
                yield part["text"]
