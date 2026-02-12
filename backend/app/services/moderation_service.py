from sqlalchemy.ext.asyncio import AsyncSession


class ModerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def review_persona(self, persona_id: str, action: str):
        """관리자 페르소나 모더레이션 (approve/block)."""
        raise NotImplementedError

    async def get_moderation_queue(self, status: str = "pending"):
        """모더레이션 대기열 조회."""
        raise NotImplementedError
