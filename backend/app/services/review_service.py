import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.models.review_cache import ReviewCache
from app.prompt.compiler import PromptCompiler
from app.prompt.persona_loader import PersonaLoader
from app.services.inference_client import InferenceClient
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.compiler = PromptCompiler()
        self.persona_loader = PersonaLoader(db)
        self.inference = InferenceClient()
        self.rag = RAGService(db)

    async def get_cached_review(self, episode_id: str, persona_id: str, spoiler_mode: str) -> ReviewCache | None:
        """캐시된 리뷰 조회."""
        result = await self.db.execute(
            select(ReviewCache).where(
                ReviewCache.episode_id == uuid.UUID(episode_id),
                ReviewCache.persona_id == uuid.UUID(persona_id),
                ReviewCache.spoiler_mode == spoiler_mode,
            )
        )
        cache = result.scalar_one_or_none()

        # 만료 체크
        if cache and cache.expires_at and cache.expires_at < datetime.now(UTC):
            await self.db.delete(cache)
            await self.db.commit()
            return None

        return cache

    async def generate_review(self, episode_id: str, persona_id: str, spoiler_mode: str) -> ReviewCache:
        """리뷰 생성 (캐시 miss 시 LLM 호출)."""
        # 1. 캐시 확인
        cached = await self.get_cached_review(episode_id, persona_id, spoiler_mode)
        if cached:
            return cached

        # 2. 에피소드 정보 로드
        ep_result = await self.db.execute(select(Episode).where(Episode.id == uuid.UUID(episode_id)))
        episode = ep_result.scalar_one_or_none()
        if episode is None:
            raise ValueError(f"Episode {episode_id} not found")

        # 3. 페르소나 로드
        persona_data = await self.persona_loader.load(uuid.UUID(persona_id))

        # 4. 근거 번들 구성
        query = f"{episode.title or ''} {episode.summary or ''}"
        evidence = await self.rag.build_evidence_bundle(
            query=query,
            webtoon_id=str(episode.webtoon_id),
            persona_id=persona_id,
        )

        # 5. 리뷰 프롬프트 구성
        messages = self.compiler.compile(
            persona=persona_data,
            lorebook_entries=persona_data.get("lorebook", []),
            session_summary=None,
            recent_messages=[],
        )

        # 리뷰 요청 메시지 추가
        review_prompt = self._build_review_prompt(episode, evidence, spoiler_mode)
        messages.append({"role": "user", "content": review_prompt})

        # 6. LLM 호출 (기본 모델 사용)
        from app.models.llm_model import LLMModel

        model_result = await self.db.execute(select(LLMModel).where(LLMModel.is_active == True).limit(1))
        llm_model = model_result.scalar_one_or_none()
        if llm_model is None:
            raise ValueError("No active LLM model available")

        result = await self.inference.generate(llm_model, messages)

        # 7. 캐시에 저장
        cache = ReviewCache(
            episode_id=uuid.UUID(episode_id),
            persona_id=uuid.UUID(persona_id),
            spoiler_mode=spoiler_mode,
            review_text=result["content"],
        )
        self.db.add(cache)
        await self.db.commit()
        await self.db.refresh(cache)
        return cache

    async def batch_precompute(self, webtoon_id: str, persona_id: str) -> int:
        """배치 프리컴퓨트: 웹툰의 모든 에피소드에 대해 리뷰 생성."""
        ep_result = await self.db.execute(
            select(Episode).where(Episode.webtoon_id == uuid.UUID(webtoon_id)).order_by(Episode.episode_number.asc())
        )
        episodes = ep_result.scalars().all()

        generated = 0
        for episode in episodes:
            for spoiler_mode in ["safe", "spoiler"]:
                try:
                    cached = await self.get_cached_review(str(episode.id), persona_id, spoiler_mode)
                    if cached is None:
                        await self.generate_review(str(episode.id), persona_id, spoiler_mode)
                        generated += 1
                except Exception:
                    logger.warning(
                        "Failed to generate review for episode %s",
                        episode.id,
                        exc_info=True,
                    )
        return generated

    @staticmethod
    def _build_review_prompt(episode: Episode, evidence: dict, spoiler_mode: str) -> str:
        """리뷰 생성 프롬프트 구성."""
        parts = [f"[리뷰 요청] 에피소드 #{episode.episode_number}"]
        if episode.title:
            parts.append(f"제목: {episode.title}")

        if spoiler_mode == "safe":
            parts.append("(스포일러 없이 리뷰해주세요)")
        else:
            parts.append("(스포일러 포함 상세 리뷰)")

        if episode.summary:
            parts.append(f"\n요약: {episode.summary}")

        # 근거 번들 추가
        if evidence.get("episode_emotions"):
            emotion_text = ", ".join(f"{e['label']}({e['intensity']:.2f})" for e in evidence["episode_emotions"][:5])
            parts.append(f"\n감정 신호: {emotion_text}")

        if evidence.get("comment_stats"):
            for cs in evidence["comment_stats"][:3]:
                parts.append(
                    f"댓글 반응: 총 {cs['total_count']}개, " f"긍정 {(cs.get('positive_ratio') or 0) * 100:.0f}%"
                )

        if evidence.get("retrieved_chunks"):
            parts.append("\n[관련 근거]")
            for chunk in evidence["retrieved_chunks"][:3]:
                parts.append(f"- {chunk['text'][:200]}")

        parts.append("\n위 정보를 바탕으로 이 에피소드의 리뷰를 작성해주세요.")
        return "\n".join(parts)
