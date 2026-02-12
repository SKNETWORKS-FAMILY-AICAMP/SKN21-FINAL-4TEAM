import uuid

from sqlalchemy.ext.asyncio import AsyncSession


class UsageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_usage(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID | None,
        llm_model_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
    ):
        """토큰 사용량 기록 + 비용 산출 + Redis 캐시 갱신."""
        raise NotImplementedError

    async def get_user_summary(self, user_id: uuid.UUID) -> dict:
        """사용자 사용량 요약 (일/월/총계)."""
        raise NotImplementedError

    async def get_user_history(self, user_id: uuid.UUID, days: int = 30) -> list[dict]:
        """일별 사용량 히스토리."""
        raise NotImplementedError

    async def get_admin_summary(self) -> dict:
        """전체 사용량 통계 (관리자용)."""
        raise NotImplementedError
