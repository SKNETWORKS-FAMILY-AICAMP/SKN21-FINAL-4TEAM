import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.core.observability import create_generation, record_llm_metrics
from app.models.llm_model import LLMModel

logger = logging.getLogger(__name__)

# RunPod Serverless SGLang은 OpenAI-compatible API를 제공
_RUNPOD_BASE_URL = "https://api.runpod.ai/v2/{endpoint_id}/openai/v1"

# max_tokens 대신 max_completion_tokens를 사용해야 하는 OpenAI 모델 접두사
# o-series 추론 모델(o1/o3/o4)과 gpt-4.1+/gpt-5+ 계열은 max_completion_tokens 필수
_OPENAI_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "o4", "gpt-4.1", "gpt-5")

# temperature 파라미터를 지원하지 않는 모델 접두사 (o-series 추론 모델만 해당)
_OPENAI_NO_TEMPERATURE_PREFIXES = ("o1", "o3", "o4")


def _openai_max_tokens_key(model_id: str) -> str:
    """모델에 따라 max_tokens 또는 max_completion_tokens 파라미터 키를 반환."""
    model = model_id.lower()
    if any(model.startswith(p) for p in _OPENAI_COMPLETION_TOKENS_PREFIXES):
        return "max_completion_tokens"
    return "max_tokens"


def _openai_supports_temperature(model_id: str) -> bool:
    """모델이 temperature 파라미터를 지원하는지 반환. o-series 추론 모델만 미지원."""
    model = model_id.lower()
    return not any(model.startswith(p) for p in _OPENAI_NO_TEMPERATURE_PREFIXES)


class InferenceClient:
    """LLM 모델 라우터. provider별 분기 처리."""

    async def generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """provider에 따라 적절한 API로 라우팅 (비스트리밍). Langfuse/Prometheus 계측 포함."""
        # Langfuse generation 시작
        generation = create_generation(
            name=f"llm_{model.provider}",
            model=model.model_id,
            input_messages=messages,
        )

        start = time.monotonic()
        try:
            match model.provider:
                case "openai":
                    result = await self._call_openai(model, messages, **kwargs)
                case "runpod":
                    result = await self._call_runpod(model, messages, **kwargs)
                case "anthropic":
                    result = await self._call_anthropic(model, messages, **kwargs)
                case "google":
                    result = await self._call_google(model, messages, **kwargs)
                case _:
                    raise ValueError(f"Unknown provider: {model.provider}")

            duration = time.monotonic() - start

            # Langfuse generation 완료
            if generation:
                generation.end(
                    output=result["content"],
                    usage={
                        "input": result.get("input_tokens", 0),
                        "output": result.get("output_tokens", 0),
                    },
                )

            # Prometheus 메트릭 기록
            record_llm_metrics(
                provider=model.provider,
                model=model.model_id,
                duration=duration,
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
            )

            return result
        except Exception as exc:
            if generation:
                generation.end(status_message=str(exc), level="ERROR")
            raise

    async def generate_stream(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """provider에 따라 SSE 스트리밍. usage_out에 토큰 수를 기록."""
        if usage_out is None:
            usage_out = {}
        match model.provider:
            case "openai":
                async for chunk in self._stream_openai(model, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case "runpod":
                async for chunk in self._stream_runpod(model, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case "anthropic":
                async for chunk in self._stream_anthropic(model, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case "google":
                async for chunk in self._stream_google(model, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case _:
                raise ValueError(f"Unknown provider: {model.provider}")

    # ── BYOK (Bring Your Own Key) ──

    async def generate_byok(
        self, provider: str, model_id: str, api_key: str, messages: list[dict], **kwargs
    ) -> dict:
        """사용자 API 키를 사용하여 LLM 호출. 토론 엔진용."""
        match provider:
            case "openai":
                return await self._call_openai_byok(model_id, api_key, messages, **kwargs)
            case "anthropic":
                return await self._call_anthropic_byok(model_id, api_key, messages, **kwargs)
            case "google":
                return await self._call_google_byok(model_id, api_key, messages, **kwargs)
            case _:
                raise ValueError(f"BYOK not supported for provider: {provider}")

    async def generate_stream_byok(
        self,
        provider: str,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """사용자 API 키로 스트리밍 호출. 토론 엔진 실시간 출력용."""
        if usage_out is None:
            usage_out = {}
        match provider:
            case "openai":
                async for chunk in self._stream_openai_byok(model_id, api_key, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case "anthropic":
                async for chunk in self._stream_anthropic_byok(model_id, api_key, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case "google":
                async for chunk in self._stream_google_byok(model_id, api_key, messages, usage_out=usage_out, **kwargs):
                    yield chunk
            case _:
                raise ValueError(f"BYOK streaming not supported for provider: {provider}")

    async def _call_openai_byok(
        self, model_id: str, api_key: str, messages: list[dict], **kwargs
    ) -> dict:
        max_key = _openai_max_tokens_key(model_id)
        body: dict = {
            "model": model_id,
            "messages": messages,
            max_key: kwargs.get("max_tokens", 1024),
        }
        # o-series 추론 모델만 temperature 미지원, gpt-4.1/gpt-5 등은 temperature 지원
        if _openai_supports_temperature(model_id):
            body["temperature"] = kwargs.get("temperature", 0.7)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
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

    async def _stream_openai_byok(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """OpenAI BYOK 스트리밍."""
        max_key = _openai_max_tokens_key(model_id)
        stream_body: dict = {
            "model": model_id,
            "messages": messages,
            max_key: kwargs.get("max_tokens", 1024),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if _openai_supports_temperature(model_id):
            stream_body["temperature"] = kwargs.get("temperature", 0.7)
        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=stream_body,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                if chunk.get("usage") and usage_out is not None:
                    usage_out["input_tokens"] = chunk["usage"].get("prompt_tokens", 0)
                    usage_out["output_tokens"] = chunk["usage"].get("completion_tokens", 0)
                delta = chunk["choices"][0].get("delta", {}) if chunk.get("choices") else {}
                if "content" in delta:
                    yield delta["content"]

    async def _call_anthropic_byok(
        self, model_id: str, api_key: str, messages: list[dict], **kwargs
    ) -> dict:
        system_prompt, api_messages = self._split_system_messages(messages)
        async with httpx.AsyncClient(timeout=60.0) as client:
            body: dict = {
                "model": model_id,
                "messages": api_messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            }
            if system_prompt:
                body["system"] = system_prompt
            response = await client.post(
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

    async def _stream_anthropic_byok(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Anthropic BYOK 스트리밍."""
        system_prompt, api_messages = self._split_system_messages(messages)
        async with httpx.AsyncClient(timeout=120.0) as client:
            body: dict = {
                "model": model_id,
                "messages": api_messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
                "stream": True,
            }
            if system_prompt:
                body["system"] = system_prompt
            async with client.stream(
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
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("type")
                    if event_type == "message_start" and usage_out is not None:
                        usage_out["input_tokens"] = event.get("message", {}).get("usage", {}).get("input_tokens", 0)
                    elif event_type == "message_delta" and usage_out is not None:
                        usage_out["output_tokens"] = event.get("usage", {}).get("output_tokens", 0)
                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta["text"]
                    elif event_type == "message_stop":
                        break

    async def _call_google_byok(
        self, model_id: str, api_key: str, messages: list[dict], **kwargs
    ) -> dict:
        system_prompt, gemini_contents = self._to_gemini_format(messages)
        async with httpx.AsyncClient(timeout=60.0) as client:
            body: dict = {
                "contents": gemini_contents,
                "generationConfig": {
                    "maxOutputTokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }
            if system_prompt:
                body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
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

    async def _stream_google_byok(
        self,
        model_id: str,
        api_key: str,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Google BYOK 스트리밍."""
        system_prompt, gemini_contents = self._to_gemini_format(messages)
        async with httpx.AsyncClient(timeout=120.0) as client:
            body: dict = {
                "contents": gemini_contents,
                "generationConfig": {
                    "maxOutputTokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }
            if system_prompt:
                body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:streamGenerateContent",
                params={"key": api_key, "alt": "sse"},
                headers={"Content-Type": "application/json"},
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("usageMetadata") and usage_out is not None:
                        meta = chunk["usageMetadata"]
                        usage_out["input_tokens"] = meta.get("promptTokenCount", 0)
                        usage_out["output_tokens"] = meta.get("candidatesTokenCount", 0)
                    candidates = chunk.get("candidates", [])
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            yield part["text"]

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

    async def _stream_openai(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """OpenAI API SSE 스트리밍. stream_options로 usage 포함."""
        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream(
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
                    "stream_options": {"include_usage": True},
                },
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                # 마지막 청크에 usage 정보 포함
                if chunk.get("usage") and usage_out is not None:
                    usage_out["input_tokens"] = chunk["usage"].get("prompt_tokens", 0)
                    usage_out["output_tokens"] = chunk["usage"].get("completion_tokens", 0)
                delta = chunk["choices"][0].get("delta", {}) if chunk.get("choices") else {}
                if "content" in delta:
                    yield delta["content"]

    # ── RunPod (SGLang — OpenAI-compatible API) ──

    async def _call_runpod(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """RunPod Serverless SGLang 호출. OpenAI-compatible 엔드포인트 사용."""
        base_url = _RUNPOD_BASE_URL.format(endpoint_id=settings.runpod_endpoint_id)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.runpod_api_key}",
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
            usage = data.get("usage", {})
            return {
                "content": choice["message"]["content"],
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "finish_reason": choice.get("finish_reason", "stop"),
            }

    async def _stream_runpod(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """RunPod SGLang SSE 스트리밍. OpenAI-compatible stream 형식."""
        base_url = _RUNPOD_BASE_URL.format(endpoint_id=settings.runpod_endpoint_id)
        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.runpod_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model.model_id,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                if chunk.get("usage") and usage_out is not None:
                    usage_out["input_tokens"] = chunk["usage"].get("prompt_tokens", 0)
                    usage_out["output_tokens"] = chunk["usage"].get("completion_tokens", 0)
                delta = chunk["choices"][0].get("delta", {}) if chunk.get("choices") else {}
                if "content" in delta:
                    yield delta["content"]

    # ── Anthropic (Messages API) ──

    async def _call_anthropic(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """Anthropic Messages API 호출."""
        system_prompt, api_messages = self._split_system_messages(messages)

        async with httpx.AsyncClient(timeout=60.0) as client:
            body: dict = {
                "model": model.model_id,
                "messages": api_messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
            }
            if system_prompt:
                body["system"] = system_prompt

            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
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

    async def _stream_anthropic(
        self,
        model: LLMModel,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Anthropic Messages API SSE 스트리밍. message_start/message_delta에서 usage 캡처."""
        system_prompt, api_messages = self._split_system_messages(messages)

        async with httpx.AsyncClient(timeout=120.0) as client:
            body: dict = {
                "model": model.model_id,
                "messages": api_messages,
                "max_tokens": kwargs.get("max_tokens", 1024),
                "temperature": kwargs.get("temperature", 0.7),
                "stream": True,
            }
            if system_prompt:
                body["system"] = system_prompt

            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")
                    # message_start에 input_tokens 포함
                    if event_type == "message_start" and usage_out is not None:
                        msg_usage = event.get("message", {}).get("usage", {})
                        usage_out["input_tokens"] = msg_usage.get("input_tokens", 0)
                    # message_delta에 output_tokens 포함
                    elif event_type == "message_delta" and usage_out is not None:
                        delta_usage = event.get("usage", {})
                        usage_out["output_tokens"] = delta_usage.get("output_tokens", 0)
                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta["text"]
                    elif event_type == "message_stop":
                        break

    # ── Google (Gemini API) ──

    async def _call_google(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """Google Gemini API 호출."""
        system_prompt, gemini_contents = self._to_gemini_format(messages)

        async with httpx.AsyncClient(timeout=60.0) as client:
            body: dict = {
                "contents": gemini_contents,
                "generationConfig": {
                    "maxOutputTokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }
            if system_prompt:
                body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model.model_id}:generateContent",
                params={"key": settings.google_api_key},
                headers={"Content-Type": "application/json"},
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

    async def _stream_google(
        self,
        model: LLMModel,
        messages: list[dict],
        usage_out: dict | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Google Gemini API SSE 스트리밍. usageMetadata에서 토큰 수 캡처."""
        system_prompt, gemini_contents = self._to_gemini_format(messages)

        async with httpx.AsyncClient(timeout=120.0) as client:
            body: dict = {
                "contents": gemini_contents,
                "generationConfig": {
                    "maxOutputTokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }
            if system_prompt:
                body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model.model_id}:streamGenerateContent",
                params={"key": settings.google_api_key, "alt": "sse"},
                headers={"Content-Type": "application/json"},
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    # usageMetadata는 마지막 청크에 포함
                    if chunk.get("usageMetadata") and usage_out is not None:
                        meta = chunk["usageMetadata"]
                        usage_out["input_tokens"] = meta.get("promptTokenCount", 0)
                        usage_out["output_tokens"] = meta.get("candidatesTokenCount", 0)

                    candidates = chunk.get("candidates", [])
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            yield part["text"]

    # ── 유틸리티 ──

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
                contents.append(
                    {
                        "role": "model",
                        "parts": [{"text": msg["content"]}],
                    }
                )
            else:
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": msg["content"]}],
                    }
                )
        return "\n\n".join(system_parts), contents
