from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.lorebook import LorebookCreate, LorebookUpdate


class LorebookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_entry(self, data: LorebookCreate, user: User):
        """로어북 항목 생성 + 임베딩 벡터 생성."""
        raise NotImplementedError

    async def update_entry(self, entry_id: int, data: LorebookUpdate, user: User):
        raise NotImplementedError

    async def delete_entry(self, entry_id: int, user: User):
        raise NotImplementedError

    async def list_by_persona(self, persona_id: str, user: User):
        raise NotImplementedError

    async def search_relevant(self, query: str, persona_id: str | None = None, webtoon_id: str | None = None):
        """벡터 유사도 검색으로 관련 로어북 항목 조회."""
        raise NotImplementedError
