from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class PolicyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_spoiler_setting(self, user: User, webtoon_id: str):
        raise NotImplementedError

    async def update_spoiler_setting(self, user: User, webtoon_id: str, mode: str, max_episode: int | None = None):
        raise NotImplementedError

    async def check_age_gate(self, user: User, age_rating: str) -> bool:
        """연령등급 게이트 검증. False면 접근 차단."""
        raise NotImplementedError

    async def build_policy_snapshot(self, user: User, webtoon_id: str | None) -> dict:
        """메시지 생성 시점 정책 상태 스냅샷."""
        raise NotImplementedError
