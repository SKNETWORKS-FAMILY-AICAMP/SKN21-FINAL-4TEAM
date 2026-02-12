from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel


class InferenceClient:
    """LLM 모델 라우터. provider별 분기 처리."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """provider에 따라 적절한 API로 라우팅."""
        match model.provider:
            case "runpod":
                return await self._call_runpod(model, messages, **kwargs)
            case "openai":
                return await self._call_openai(model, messages, **kwargs)
            case "anthropic":
                return await self._call_anthropic(model, messages, **kwargs)
            case "google":
                return await self._call_google(model, messages, **kwargs)
            case _:
                raise ValueError(f"Unknown provider: {model.provider}")

    async def _call_runpod(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """RunPod Serverless + SGLang 호출."""
        raise NotImplementedError

    async def _call_openai(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """OpenAI API 호출."""
        raise NotImplementedError

    async def _call_anthropic(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """Anthropic API 호출."""
        raise NotImplementedError

    async def _call_google(self, model: LLMModel, messages: list[dict], **kwargs) -> dict:
        """Google Gemini API 호출."""
        raise NotImplementedError
