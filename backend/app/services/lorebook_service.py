import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lorebook_entry import LorebookEntry
from app.models.user import User
from app.schemas.lorebook import LorebookCreate, LorebookUpdate

# 프로토타입: 실제 임베딩 대신 제로벡터 사용 (Phase 3에서 BGE-M3 연동)
ZERO_EMBEDDING = [0.0] * 1024


class LorebookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_persona(self, persona_id: uuid.UUID, skip: int = 0, limit: int = 20) -> dict:
        """페르소나에 속한 로어북 항목 목록."""
        count_query = (
            select(func.count())
            .select_from(LorebookEntry)
            .where(LorebookEntry.persona_id == persona_id)
        )
        total = (await self.db.execute(count_query)).scalar()

        query = (
            select(LorebookEntry)
            .where(LorebookEntry.persona_id == persona_id)
            .order_by(LorebookEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def get_entry(self, entry_id: int) -> LorebookEntry:
        """로어북 항목 단건 조회."""
        return await self._get_or_404(entry_id)

    async def create_entry(self, data: LorebookCreate, user: User) -> LorebookEntry:
        """로어북 항목 생성 + 제로벡터 임베딩."""
        if data.persona_id is None and data.webtoon_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either persona_id or webtoon_id is required",
            )

        entry = LorebookEntry(
            persona_id=data.persona_id,
            webtoon_id=data.webtoon_id,
            created_by=user.id,
            title=data.title,
            content=data.content,
            tags=data.tags,
            embedding=ZERO_EMBEDDING,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def update_entry(self, entry_id: int, data: LorebookUpdate, user: User) -> LorebookEntry:
        """로어북 항목 수정 (소유자만)."""
        entry = await self._get_or_404(entry_id)
        self._check_ownership(entry, user)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(entry, field, value)
        entry.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def delete_entry(self, entry_id: int, user: User) -> None:
        """로어북 항목 삭제 (소유자만)."""
        entry = await self._get_or_404(entry_id)
        self._check_ownership(entry, user)
        await self.db.delete(entry)
        await self.db.commit()

    async def search_relevant(self, query: str, persona_id: uuid.UUID | None = None, webtoon_id: uuid.UUID | None = None):
        """벡터 유사도 검색으로 관련 로어북 항목 조회. Phase 3에서 구현."""
        raise NotImplementedError

    # ── 헬퍼 ──

    async def _get_or_404(self, entry_id: int) -> LorebookEntry:
        result = await self.db.execute(select(LorebookEntry).where(LorebookEntry.id == entry_id))
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lorebook entry not found")
        return entry

    @staticmethod
    def _check_ownership(entry: LorebookEntry, user: User) -> None:
        if entry.created_by != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner")
