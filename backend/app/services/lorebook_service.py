import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lorebook_entry import LorebookEntry
from app.models.user import User
from app.pipeline.embedding import EmbeddingService, get_embedding_service
from app.pipeline.pii import PIIDetector, get_pii_detector
from app.schemas.lorebook import LorebookCreate, LorebookUpdate

logger = logging.getLogger(__name__)


class LorebookService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        pii_detector: PIIDetector | None = None,
    ):
        self.db = db
        self._embedding = embedding_service
        self._pii = pii_detector

    @property
    def embedding(self) -> EmbeddingService:
        if self._embedding is None:
            self._embedding = get_embedding_service()
        return self._embedding

    @property
    def pii(self) -> PIIDetector:
        if self._pii is None:
            self._pii = get_pii_detector()
        return self._pii

    async def list_by_persona(self, persona_id: uuid.UUID, skip: int = 0, limit: int = 20) -> dict:
        """페르소나에 속한 로어북 항목 목록."""
        count_query = select(func.count()).select_from(LorebookEntry).where(LorebookEntry.persona_id == persona_id)
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
        """로어북 항목 생성 + PII 마스킹 + BGE-M3 임베딩."""
        if data.persona_id is None and data.webtoon_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either persona_id or webtoon_id is required",
            )

        # PII 마스킹 (개인정보 제거)
        safe_title = self.pii.mask(data.title)
        safe_content = self.pii.mask(data.content)

        # 제목 + 본문으로 임베딩 생성
        embed_text = f"{safe_title}: {safe_content}"
        embedding_vec = self.embedding.embed(embed_text)

        entry = LorebookEntry(
            persona_id=data.persona_id,
            webtoon_id=data.webtoon_id,
            created_by=user.id,
            title=safe_title,
            content=safe_content,
            tags=data.tags,
            embedding=embedding_vec,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def update_entry(self, entry_id: int, data: LorebookUpdate, user: User) -> LorebookEntry:
        """로어북 항목 수정 (소유자만). PII 마스킹 + 제목/본문 변경 시 임베딩 재생성."""
        entry = await self._get_or_404(entry_id)
        self._check_ownership(entry, user)

        update_data = data.model_dump(exclude_unset=True)
        # PII 마스킹 (텍스트 필드)
        if "title" in update_data:
            update_data["title"] = self.pii.mask(update_data["title"])
        if "content" in update_data:
            update_data["content"] = self.pii.mask(update_data["content"])
        for field, value in update_data.items():
            setattr(entry, field, value)
        entry.updated_at = datetime.now(UTC)

        # 제목 또는 본문이 변경되면 임베딩 재생성
        if "title" in update_data or "content" in update_data:
            embed_text = f"{entry.title}: {entry.content}"
            entry.embedding = self.embedding.embed(embed_text)

        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def delete_entry(self, entry_id: int, user: User) -> None:
        """로어북 항목 삭제 (소유자만)."""
        entry = await self._get_or_404(entry_id)
        self._check_ownership(entry, user)
        await self.db.delete(entry)
        await self.db.commit()

    async def search_relevant(
        self, query: str, persona_id: uuid.UUID | None = None, webtoon_id: uuid.UUID | None = None, top_k: int = 10
    ) -> list[LorebookEntry]:
        """벡터 유사도 검색으로 관련 로어북 항목 조회."""
        query_vec = self.embedding.embed(query)

        stmt = select(LorebookEntry).order_by(LorebookEntry.embedding.cosine_distance(query_vec)).limit(top_k)

        conditions = []
        if persona_id:
            conditions.append(LorebookEntry.persona_id == persona_id)
        if webtoon_id:
            conditions.append(LorebookEntry.webtoon_id == webtoon_id)
        if conditions:
            stmt = stmt.where(or_(*conditions))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── 헬퍼 ──

    async def _get_or_404(self, entry_id: int) -> LorebookEntry:
        result = await self.db.execute(
            select(LorebookEntry).options(selectinload(LorebookEntry.persona)).where(LorebookEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lorebook entry not found")
        return entry

    @staticmethod
    def _check_ownership(entry: LorebookEntry, user: User) -> None:
        # 항목 생성자이거나, 해당 페르소나의 소유자이면 허용
        if entry.created_by == user.id:
            return
        if entry.persona_id and entry.persona and entry.persona.created_by == user.id:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner")
