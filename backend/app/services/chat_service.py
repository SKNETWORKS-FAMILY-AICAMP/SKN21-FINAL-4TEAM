from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, user: User, persona_id: str, webtoon_id: str | None = None, llm_model_id: str | None = None):
        raise NotImplementedError

    async def send_message(self, session_id: str, user: User, content: str):
        """메시지 처리 → LLM 호출 → SSE 스트리밍."""
        raise NotImplementedError

    async def get_user_sessions(self, user: User):
        raise NotImplementedError
