"""LLM provider 추상 기반 클래스."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class BaseProvider(ABC):
    """LLM provider 추상 기반 클래스.

    모든 provider는 이 클래스를 상속하고 4개의 추상 메서드를 구현해야 한다.
    플랫폼 API 키 호출(generate/stream)과 BYOK 호출(generate_byok/stream_byok)을 분리.
    """

    @abstractmethod
    async def generate(self, model_id: str, messages: list[dict], **kwargs) -> dict:
        """플랫폼 API 키로 LLM 호출 (비스트리밍).

        Returns:
            {'content': str, 'input_tokens': int, 'output_tokens': int, 'finish_reason': str}
        """
        ...

    @abstractmethod
    async def generate_byok(self, model_id: str, api_key: str, messages: list[dict], **kwargs) -> dict:
        """사용자 제공 API 키(BYOK)로 LLM 호출 (비스트리밍).

        Returns:
            {'content': str, 'input_tokens': int, 'output_tokens': int, 'finish_reason': str}
        """
        ...

    @abstractmethod
    async def stream(
        self, model_id: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """플랫폼 API 키로 SSE 스트리밍 호출.

        Args:
            usage_out: 토큰 사용량을 채울 딕셔너리 (input_tokens, output_tokens 키)
        """
        ...

    @abstractmethod
    async def stream_byok(
        self, model_id: str, api_key: str, messages: list[dict], usage_out: dict, **kwargs
    ) -> AsyncGenerator[str, None]:
        """BYOK SSE 스트리밍 호출.

        Args:
            usage_out: 토큰 사용량을 채울 딕셔너리 (input_tokens, output_tokens 키)
        """
        ...
