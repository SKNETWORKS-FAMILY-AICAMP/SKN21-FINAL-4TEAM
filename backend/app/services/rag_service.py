import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment_stat import CommentStat
from app.models.episode import Episode
from app.models.episode_embedding import EpisodeEmbedding
from app.models.episode_emotion import EpisodeEmotion
from app.models.lorebook_entry import LorebookEntry
from app.pipeline.embedding import EmbeddingService, get_embedding_service
from app.pipeline.reranker import Reranker, get_reranker

logger = logging.getLogger(__name__)


class RAGService:
    """하이브리드 검색 + 근거 번들 구성.

    1단계: pgvector 벡터 유사도로 후보 검색 (over-fetch)
    2단계: cross-encoder 리랭킹으로 최종 정렬
    3단계: 근거 번들(에피소드 정보 + 감정 + 댓글 + 로어북) 구성
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        reranker: Reranker | None = None,
    ):
        self.db = db
        self._embedding = embedding_service
        self._reranker = reranker

    @property
    def embedding(self) -> EmbeddingService:
        if self._embedding is None:
            self._embedding = get_embedding_service()
        return self._embedding

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = get_reranker()
        return self._reranker

    async def retrieve(
        self,
        query: str,
        webtoon_id: str | uuid.UUID | None = None,
        top_k: int = 5,
        over_fetch_factor: int = 3,
    ) -> list[dict]:
        """하이브리드 검색: pgvector 벡터 유사도 → cross-encoder 리랭킹."""
        # 1. 쿼리 임베딩
        query_vec = self.embedding.embed(query)

        # 2. pgvector 코사인 유사도로 후보 over-fetch
        fetch_k = top_k * over_fetch_factor
        stmt = (
            select(
                EpisodeEmbedding.id,
                EpisodeEmbedding.episode_id,
                EpisodeEmbedding.chunk_type,
                EpisodeEmbedding.chunk_text,
                EpisodeEmbedding.embedding.cosine_distance(query_vec).label("distance"),
            )
            .order_by("distance")
            .limit(fetch_k)
        )

        if webtoon_id:
            stmt = stmt.join(Episode, EpisodeEmbedding.episode_id == Episode.id).where(
                Episode.webtoon_id == uuid.UUID(str(webtoon_id))
            )

        result = await self.db.execute(stmt)
        candidates = result.all()

        if not candidates:
            return []

        # 3. cross-encoder 리랭킹
        candidate_texts = [c.chunk_text for c in candidates]
        reranked = self.reranker.rerank(query, candidate_texts, top_k=top_k)

        # 4. 원본 메타데이터와 매핑
        results = []
        for item in reranked:
            original = candidates[item["index"]]
            results.append(
                {
                    "embedding_id": original.id,
                    "episode_id": str(original.episode_id),
                    "chunk_type": original.chunk_type,
                    "text": original.chunk_text,
                    "vector_distance": float(original.distance),
                    "rerank_score": item["score"],
                }
            )

        return results

    async def build_evidence_bundle(
        self,
        query: str,
        webtoon_id: str | uuid.UUID | None = None,
        persona_id: str | uuid.UUID | None = None,
    ) -> dict:
        """근거 번들 구성: 에피소드 임베딩 + 감정 신호 + 댓글 통계 + 로어북."""
        bundle: dict = {
            "retrieved_chunks": [],
            "episode_emotions": [],
            "comment_stats": [],
            "lorebook_entries": [],
        }

        # 1. 벡터 검색으로 관련 청크 가져오기
        retrieved = await self.retrieve(query, webtoon_id=webtoon_id, top_k=5)
        bundle["retrieved_chunks"] = retrieved

        if not retrieved:
            # 검색 결과 없으면 로어북만 반환
            bundle["lorebook_entries"] = await self._fetch_lorebook(query, persona_id, webtoon_id)
            return bundle

        # 2. 검색된 에피소드 ID 수집
        episode_ids = list({uuid.UUID(r["episode_id"]) for r in retrieved})

        # 3. 에피소드 감정 신호 가져오기
        emotion_result = await self.db.execute(
            select(EpisodeEmotion)
            .where(EpisodeEmotion.episode_id.in_(episode_ids))
            .order_by(EpisodeEmotion.intensity.desc())
        )
        emotions = emotion_result.scalars().all()
        bundle["episode_emotions"] = [
            {
                "episode_id": str(e.episode_id),
                "label": e.emotion_label,
                "intensity": e.intensity,
                "confidence": e.confidence,
            }
            for e in emotions
        ]

        # 4. 댓글 통계 가져오기
        comment_result = await self.db.execute(select(CommentStat).where(CommentStat.episode_id.in_(episode_ids)))
        comments = comment_result.scalars().all()
        bundle["comment_stats"] = [
            {
                "episode_id": str(c.episode_id),
                "total_count": c.total_count,
                "positive_ratio": c.positive_ratio,
                "negative_ratio": c.negative_ratio,
                "top_emotions": c.top_emotions,
            }
            for c in comments
        ]

        # 5. 로어북 항목 가져오기
        bundle["lorebook_entries"] = await self._fetch_lorebook(query, persona_id, webtoon_id)

        return bundle

    async def _fetch_lorebook(
        self,
        query: str,
        persona_id: str | uuid.UUID | None,
        webtoon_id: str | uuid.UUID | None,
    ) -> list[dict]:
        """로어북 항목 벡터 검색."""
        query_vec = self.embedding.embed(query)

        stmt = (
            select(
                LorebookEntry.id,
                LorebookEntry.title,
                LorebookEntry.content,
                LorebookEntry.tags,
                LorebookEntry.embedding.cosine_distance(query_vec).label("distance"),
            )
            .order_by("distance")
            .limit(10)
        )

        conditions = []
        if persona_id:
            conditions.append(LorebookEntry.persona_id == uuid.UUID(str(persona_id)))
        if webtoon_id:
            conditions.append(LorebookEntry.webtoon_id == uuid.UUID(str(webtoon_id)))

        if conditions:
            from sqlalchemy import or_

            stmt = stmt.where(or_(*conditions))

        result = await self.db.execute(stmt)
        entries = result.all()

        return [
            {
                "id": e.id,
                "title": e.title,
                "content": e.content,
                "tags": e.tags or [],
                "distance": float(e.distance),
            }
            for e in entries
        ]
