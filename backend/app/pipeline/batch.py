"""배치 파이프라인: 에피소드 전처리 (감정 분석, 임베딩 생성, 리뷰 프리컴퓨트).

사용법:
    python -m app.pipeline.batch --webtoon-id <UUID> [--skip-emotions] [--skip-embeddings] [--skip-reviews]

또는 코드에서:
    from app.pipeline.batch import BatchPipeline
    pipeline = BatchPipeline(db)
    await pipeline.process_webtoon(webtoon_id)
"""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.models.episode_embedding import EpisodeEmbedding
from app.models.episode_emotion import EpisodeEmotion
from app.pipeline.embedding import EmbeddingService, get_embedding_service
from app.pipeline.emotion import EmotionAnalyzer, get_emotion_analyzer
from app.pipeline.korean_nlp import KoreanNLP, get_korean_nlp

logger = logging.getLogger(__name__)


class BatchPipeline:
    """에피소드 배치 전처리 파이프라인."""

    def __init__(
        self,
        db: AsyncSession,
        emotion_analyzer: EmotionAnalyzer | None = None,
        embedding_service: EmbeddingService | None = None,
        korean_nlp: KoreanNLP | None = None,
    ):
        self.db = db
        self._emotion = emotion_analyzer
        self._embedding = embedding_service
        self._korean_nlp = korean_nlp

    @property
    def emotion(self) -> EmotionAnalyzer:
        if self._emotion is None:
            self._emotion = get_emotion_analyzer()
        return self._emotion

    @property
    def embedding(self) -> EmbeddingService:
        if self._embedding is None:
            self._embedding = get_embedding_service()
        return self._embedding

    @property
    def korean_nlp(self) -> KoreanNLP:
        if self._korean_nlp is None:
            self._korean_nlp = get_korean_nlp()
        return self._korean_nlp

    async def process_webtoon(
        self,
        webtoon_id: uuid.UUID,
        skip_emotions: bool = False,
        skip_embeddings: bool = False,
    ) -> dict:
        """웹툰의 모든 에피소드를 배치 처리."""
        result = await self.db.execute(
            select(Episode).where(Episode.webtoon_id == webtoon_id).order_by(Episode.episode_number.asc())
        )
        episodes = result.scalars().all()

        if not episodes:
            logger.warning("No episodes found for webtoon %s", webtoon_id)
            return {"processed": 0, "errors": 0}

        logger.info("Processing %d episodes for webtoon %s", len(episodes), webtoon_id)

        processed = 0
        errors = 0

        for episode in episodes:
            try:
                await self.process_episode(
                    episode,
                    skip_emotions=skip_emotions,
                    skip_embeddings=skip_embeddings,
                )
                processed += 1
            except Exception:
                errors += 1
                logger.error(
                    "Failed to process episode %s (#%d)",
                    episode.id,
                    episode.episode_number,
                    exc_info=True,
                )

        await self.db.commit()
        logger.info(
            "Batch complete: %d processed, %d errors",
            processed,
            errors,
        )
        return {"processed": processed, "errors": errors}

    async def process_episode(
        self,
        episode: Episode,
        skip_emotions: bool = False,
        skip_embeddings: bool = False,
    ) -> None:
        """단일 에피소드 처리: 감정 분석 + 임베딩 생성."""
        text = self._get_episode_text(episode)
        if not text:
            logger.debug("Episode %s has no text, skipping", episode.id)
            return

        if not skip_emotions:
            await self._analyze_emotions(episode, text)

        if not skip_embeddings:
            await self._generate_embeddings(episode, text)

    async def _analyze_emotions(self, episode: Episode, text: str) -> None:
        """에피소드 감정 분석 → episode_emotions 저장."""
        # 이미 분석된 에피소드인지 체크
        existing = await self.db.execute(select(EpisodeEmotion).where(EpisodeEmotion.episode_id == episode.id).limit(1))
        if existing.scalar_one_or_none() is not None:
            logger.debug("Episode %s already has emotions, skipping", episode.id)
            return

        emotions = self.emotion.analyze(text, top_k=10, threshold=0.2)

        for em in emotions:
            emotion_record = EpisodeEmotion(
                episode_id=episode.id,
                emotion_label=em["label"],
                intensity=em["intensity"],
                confidence=em["confidence"],
                model_version="kote-v1",
            )
            self.db.add(emotion_record)

        logger.debug(
            "Episode #%d: %d emotions detected",
            episode.episode_number,
            len(emotions),
        )

    async def _generate_embeddings(self, episode: Episode, text: str) -> None:
        """에피소드 텍스트를 청크로 분할 → 임베딩 생성 → episode_embeddings 저장."""
        # 이미 임베딩이 있는지 체크
        existing = await self.db.execute(
            select(EpisodeEmbedding).where(EpisodeEmbedding.episode_id == episode.id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug("Episode %s already has embeddings, skipping", episode.id)
            return

        # 문장 분리로 청크 생성
        sentences = self.korean_nlp.split_sentences(text)
        chunks = self._merge_sentences_to_chunks(sentences, max_length=500)

        if not chunks:
            return

        # 배치 임베딩
        embeddings = self.embedding.embed_batch(chunks)

        for chunk_text, embedding_vec in zip(chunks, embeddings, strict=False):
            record = EpisodeEmbedding(
                episode_id=episode.id,
                chunk_type="summary",
                chunk_text=chunk_text,
                embedding=embedding_vec,
            )
            self.db.add(record)

        logger.debug(
            "Episode #%d: %d chunks embedded",
            episode.episode_number,
            len(chunks),
        )

    @staticmethod
    def _get_episode_text(episode: Episode) -> str:
        """에피소드에서 분석 대상 텍스트 추출."""
        parts = []
        if episode.title:
            parts.append(episode.title)
        if episode.summary:
            parts.append(episode.summary)
        return " ".join(parts)

    @staticmethod
    def _merge_sentences_to_chunks(sentences: list[str], max_length: int = 500) -> list[str]:
        """짧은 문장을 합쳐서 max_length 이하의 청크로 구성."""
        if not sentences:
            return []

        chunks = []
        current = []
        current_len = 0

        for sent in sentences:
            sent_len = len(sent)
            if current_len + sent_len > max_length and current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            current.append(sent)
            current_len += sent_len

        if current:
            chunks.append(" ".join(current))

        return chunks


# ── CLI 엔트리포인트 ──


async def _run_batch(webtoon_id: str, skip_emotions: bool, skip_embeddings: bool):
    from app.core.database import async_session

    async with async_session() as db:
        pipeline = BatchPipeline(db)
        result = await pipeline.process_webtoon(
            uuid.UUID(webtoon_id),
            skip_emotions=skip_emotions,
            skip_embeddings=skip_embeddings,
        )
        print(f"Done: {result}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Episode batch preprocessing pipeline")
    parser.add_argument("--webtoon-id", required=True, help="Webtoon UUID")
    parser.add_argument("--skip-emotions", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_batch(args.webtoon_id, args.skip_emotions, args.skip_embeddings))
