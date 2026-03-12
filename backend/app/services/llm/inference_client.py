import logging
import time
from collections.abc import AsyncGenerator

import httpx

from app.core.config import settings
from app.core.observability import create_generation, record_llm_metrics
from app.models.llm_model import LLMModel
from app.services.llm.providers import AnthropicProvider, GoogleProvider, OpenAIProvider, RunPodProvider
from app.services.llm.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class InferenceClient:
    """LLM 모델 라우터. provider별 분기 처리를 각 Provider 클래스에 위임.

    HTTP 연결 풀을 인스턴스 수준에서 공유해 매 LLM 호출마다 TCP/TLS 핸드셰이크를 생략.
    BYOK 스트리밍 호출 20개를 동시에 처리할 수 있는 커넥션 풀 설정.
    """

    def __init__(self) -> None:
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        self._http = httpx.AsyncClient(timeout=120.0, limits=limits)

        # 공유 HTTP 클라이언트를 provider에 주입해 커넥션 풀을 재사용
        self._providers: dict[str, BaseProvider] = {
            "openai": OpenAIProvider(http=self._http),
            "anthropic": AnthropicProvider(http=self._http),
            "google": GoogleProvider(http=self._http),
            "runpod": RunPodProvider(http=self._http),
        }

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "InferenceClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    # ── 퍼블릭 인터페이스 ──

    async def generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """provider에 따라 적절한 API로 라우팅 (비스트리밍). Langfuse/Prometheus 계측 포함."""
        generation = create_generation(
            name=f"llm_{model.provider}",
            model=model.model_id,
            input_messages=messages,
        )

        start = time.monotonic()
        try:
            result = await self._route_generate(model, messages, **kwargs)
            duration = time.monotonic() - start

            if generation:
                generation.end(
                    output=result["content"],
                    usage={
                        "input": result.get("input_tokens", 0),
                        "output": result.get("output_tokens", 0),
                    },
                )

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
        async for chunk in self._route_stream(model, messages, usage_out, **kwargs):
            yield chunk

    async def generate_byok(
        self, provider: str, model_id: str, api_key: str, messages: list[dict], **kwargs
    ) -> dict:
        """사용자 API 키를 사용하여 LLM 호출. 토론 엔진용."""
        p = self._providers.get(provider)
        if p is None:
            raise ValueError(f"BYOK not supported for provider: {provider}")
        return await p.generate_byok(model_id, api_key, messages, **kwargs)

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
        p = self._providers.get(provider)
        if p is None:
            raise ValueError(f"BYOK streaming not supported for provider: {provider}")
        async for chunk in p.stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    # ── 내부 라우팅 ──

    async def _route_generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        p = self._providers.get(model.provider)
        if p is None:
            raise ValueError(f"Unknown provider: {model.provider}")
        return await p.generate(model.model_id, messages, **kwargs)

    async def _route_stream(
        self, model: LLMModel, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        p = self._providers.get(model.provider)
        if p is None:
            raise ValueError(f"Unknown provider: {model.provider}")
        async for chunk in p.stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    # ── 하위 호환 위임 메서드 ──
    # debate_orchestrator.py 등 기존 코드가 직접 참조하는 메서드를 유지.

    async def _call_openai(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        return await self._providers["openai"].generate(model.model_id, messages, **kwargs)

    async def _call_openai_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        return await self._providers["openai"].generate_byok(model_id, api_key, messages, **kwargs)

    async def _call_anthropic(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        return await self._providers["anthropic"].generate(model.model_id, messages, **kwargs)

    async def _call_anthropic_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        return await self._providers["anthropic"].generate_byok(model_id, api_key, messages, **kwargs)

    async def _call_google(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        return await self._providers["google"].generate(model.model_id, messages, **kwargs)

    async def _call_google_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        return await self._providers["google"].generate_byok(model_id, api_key, messages, **kwargs)

    async def _call_runpod(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        return await self._providers["runpod"].generate(model.model_id, messages, **kwargs)

    async def _stream_openai(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["openai"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_openai_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["openai"].stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_anthropic(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["anthropic"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_anthropic_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["anthropic"].stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_google(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["google"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_google_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["google"].stream_byok(model_id, api_key, messages, usage_out, **kwargs):
            yield chunk

    async def _stream_runpod(
        self, model: LLMModel, messages: list[dict], usage_out: dict | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        if usage_out is None:
            usage_out = {}
        async for chunk in self._providers["runpod"].stream(model.model_id, messages, usage_out, **kwargs):
            yield chunk

    # ── 유틸리티 (기존 테스트 및 외부 코드가 참조) ──

    @staticmethod
    def _split_system_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages에서 system 메시지를 분리."""
        from app.services.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider._split_system_messages(messages)

    @staticmethod
    def _to_gemini_format(messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 형식 messages를 Gemini contents 형식으로 변환."""
        from app.services.llm.providers.google_provider import GoogleProvider

        return GoogleProvider._to_gemini_format(messages)

    @staticmethod
    async def _iter_openai_sse(response: "httpx.Response", usage_out: dict) -> AsyncGenerator[str, None]:
        from app.services.llm.providers.openai_provider import _iter_openai_sse

        async for chunk in _iter_openai_sse(response, usage_out):
            yield chunk

    @staticmethod
    async def _iter_anthropic_sse(response: "httpx.Response", usage_out: dict) -> AsyncGenerator[str, None]:
        from app.services.llm.providers.anthropic_provider import _iter_anthropic_sse

        async for chunk in _iter_anthropic_sse(response, usage_out):
            yield chunk

    @staticmethod
    async def _iter_google_sse(response: "httpx.Response", usage_out: dict) -> AsyncGenerator[str, None]:
        from app.services.llm.providers.google_provider import _iter_google_sse

        async for chunk in _iter_google_sse(response, usage_out):
            yield chunk
