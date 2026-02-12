import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.models.llm_model import LLMModel


class InferenceClient:
    """LLM 모델 라우터. provider별 분기 처리."""

    async def generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """provider에 따라 적절한 API로 라우팅 (비스트리밍)."""
        match model.provider:
            case "openai":
                return await self._call_openai(model, messages, **kwargs)
            case "runpod":
                return await self._call_runpod(model, messages, **kwargs)
            case "anthropic":
                return await self._call_anthropic(model, messages, **kwargs)
            case "google":
                return await self._call_google(model, messages, **kwargs)
            case _:
                raise ValueError(f"Unknown provider: {model.provider}")

    async def generate_stream(self, model: LLMModel, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        """provider에 따라 SSE 스트리밍."""
        match model.provider:
            case "openai":
                async for chunk in self._stream_openai(model, messages, **kwargs):
                    yield chunk
            case _:
                # 비스트리밍 폴백: 한 번에 전체 응답 반환
                result = await self.generate(model, messages, **kwargs)
                yield result["content"]

    # ── OpenAI ──

    async def _call_openai(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """OpenAI API 호출 (비스트리밍)."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model.model_id,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                },
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

    async def _stream_openai(self, model: LLMModel, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        """OpenAI API SSE 스트리밍."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model.model_id,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]

    # ── RunPod (Phase 3+ 구현 예정) ──

    async def _call_runpod(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        raise NotImplementedError("RunPod provider not yet implemented")

    # ── Anthropic (Phase 3+ 구현 예정) ──

    async def _call_anthropic(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        raise NotImplementedError("Anthropic provider not yet implemented")

    # ── Google (Phase 3+ 구현 예정) ──

    async def _call_google(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        raise NotImplementedError("Google provider not yet implemented")
