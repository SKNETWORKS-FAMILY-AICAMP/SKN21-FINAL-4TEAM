from sqlalchemy.ext.asyncio import AsyncSession


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_cached_review(self, episode_id: str, persona_id: str, spoiler_mode: str):
        """캐시된 리뷰 조회."""
        raise NotImplementedError

    async def generate_review(self, episode_id: str, persona_id: str, spoiler_mode: str):
        """리뷰 생성 (캐시 miss 시 LLM 호출)."""
        raise NotImplementedError

    async def batch_precompute(self, webtoon_id: str, persona_id: str):
        """배치 프리컴퓨트."""
        raise NotImplementedError
