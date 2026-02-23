"""AI 에이전트 스케줄러.

BatchScheduler와 같은 패턴. 2가지 트리거:
1. 이벤트 기반: 새 게시글 → 페르소나 댓글 반응
2. 주기 기반: 활성 페르소나의 자발적 게시글 생성 (5분 간격)
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.board_post import BoardPost
from app.models.persona_lounge_config import PersonaLoungeConfig

logger = logging.getLogger(__name__)

# 자발적 게시글 생성 주기 (초)
AUTONOMOUS_POST_INTERVAL = 300  # 5분


class AgentScheduler:
    """인메모리 에이전트 스케줄러. asyncio.Queue + worker loop."""

    _instance = None

    def __init__(self):
        self._post_queue: asyncio.Queue[uuid.UUID] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._periodic_task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> "AgentScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self):
        """워커 태스크 시작 (lifespan에서 호출)."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._event_worker())
            self._periodic_task = asyncio.create_task(self._periodic_worker())
            logger.info("AgentScheduler started")

    def stop(self):
        """워커 태스크 중지."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        if self._periodic_task:
            self._periodic_task.cancel()
        logger.info("AgentScheduler stopped")

    async def enqueue_post(self, post_id: uuid.UUID) -> None:
        """새 게시글 이벤트를 큐에 추가."""
        await self._post_queue.put(post_id)
        logger.debug("Post %s enqueued for agent reaction", post_id)

    async def _event_worker(self):
        """이벤트 기반: 새 게시글 → 페르소나 반응."""
        while self._running:
            try:
                post_id = await asyncio.wait_for(self._post_queue.get(), timeout=5.0)
                await self._handle_new_post(post_id)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Event worker error", exc_info=True)

    async def _periodic_worker(self):
        """주기 기반: 자발적 게시글 생성 + 일일 리셋."""
        while self._running:
            try:
                await asyncio.sleep(AUTONOMOUS_POST_INTERVAL)
                await self._generate_autonomous_posts()
                await self._reset_daily_counters_if_needed()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Periodic worker error", exc_info=True)

    async def _handle_new_post(self, post_id: uuid.UUID) -> None:
        """새 게시글에 대한 페르소나 반응 처리."""
        from app.core.database import async_session
        from app.services.agent_activity_service import AgentActivityService

        try:
            async with async_session() as db:
                result = await db.execute(select(BoardPost).where(BoardPost.id == post_id))
                post = result.scalar_one_or_none()
                if post is None or post.is_hidden:
                    return

                # AI가 쓴 글에는 반응하지 않음 (무한 루프 방지)
                if post.is_ai_generated:
                    return

                service = AgentActivityService(db)
                comments = await service.process_new_post(post)
                if comments:
                    await db.commit()
                    logger.info("Agent reactions: %d comments for post %s", len(comments), post_id)
        except Exception:
            logger.error("Failed to handle post %s", post_id, exc_info=True)

    async def _generate_autonomous_posts(self) -> None:
        """active 레벨 페르소나의 자발적 게시글 생성."""
        from app.core.database import async_session
        from app.services.agent_activity_service import AgentActivityService

        try:
            async with async_session() as db:
                q = select(PersonaLoungeConfig).where(
                    PersonaLoungeConfig.is_active == True,
                    PersonaLoungeConfig.activity_level == "active",
                    PersonaLoungeConfig.actions_today < PersonaLoungeConfig.daily_action_limit,
                    PersonaLoungeConfig.posts_today < PersonaLoungeConfig.daily_post_limit,
                )
                result = await db.execute(q)
                configs = list(result.scalars().all())

                if not configs:
                    return

                service = AgentActivityService(db)
                for config in configs:
                    try:
                        post = await service.generate_persona_post(config)
                        if post:
                            logger.info("Autonomous post by persona %s", config.persona_id)
                    except Exception:
                        logger.warning("Autonomous post failed for %s", config.persona_id, exc_info=True)
        except Exception:
            logger.error("Autonomous post generation failed", exc_info=True)

    async def _reset_daily_counters_if_needed(self) -> None:
        """자정이 지났으면 actions_today를 리셋."""
        from app.core.database import async_session

        now = datetime.now(UTC)
        # 간단한 체크: 매 주기마다 last_action_at이 오늘이 아닌 config의 카운터를 리셋
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            async with async_session() as db:
                await db.execute(
                    update(PersonaLoungeConfig)
                    .where(
                        PersonaLoungeConfig.actions_today > 0,
                        PersonaLoungeConfig.last_action_at < today,
                    )
                    .values(
                        actions_today=0,
                        posts_today=0,
                        comments_today=0,
                        chats_today=0,
                    )
                )
                await db.commit()
        except Exception:
            logger.error("Daily counter reset failed", exc_info=True)
