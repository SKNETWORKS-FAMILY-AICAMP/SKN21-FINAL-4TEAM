"""자동 매칭 백그라운드 태스크.

10초마다 debate_match_queue를 확인해 debate_queue_timeout_seconds 초과 엔트리를
플랫폼 에이전트와 자동 매칭.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_match_queue import DebateMatchQueue
from app.services.debate_engine import run_debate
from app.services.debate_queue_broadcast import publish_queue_event

logger = logging.getLogger(__name__)

_CHECK_INTERVAL = 10  # 초


class DebateAutoMatcher:
    """싱글톤 자동 매칭 태스크. BatchScheduler / AgentScheduler와 동일 패턴."""

    _instance = None

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> "DebateAutoMatcher":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        """lifespan에서 호출."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("DebateAutoMatcher started")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("DebateAutoMatcher stopped")

    async def _loop(self) -> None:
        # 시작 직후 한 번 즉시 정리 (서버 재시작 후 잔류 상태 초기화)
        try:
            await self._check_stale_entries()
            await self._check_stuck_matches()
        except Exception:
            logger.exception("DebateAutoMatcher startup cleanup error")

        while self._running:
            try:
                await self._check_stale_entries()
                await self._check_stuck_matches()
            except Exception:
                logger.exception("DebateAutoMatcher loop error")
            await asyncio.sleep(_CHECK_INTERVAL)

    async def _check_stuck_matches(self) -> None:
        """pending/waiting_agent 상태로 오래 머문 매치를 error로 처리."""
        timeout = getattr(settings, "debate_pending_timeout_seconds", 600)
        cutoff = datetime.now(UTC) - timedelta(seconds=timeout)
        async with async_session() as db:
            result = await db.execute(
                update(DebateMatch)
                .where(
                    DebateMatch.status.in_(["pending", "waiting_agent"]),
                    DebateMatch.created_at < cutoff,
                )
                .values(status="error")
                .returning(DebateMatch.id)
            )
            rows = result.fetchall()
            if rows:
                logger.warning("Cleaned up %d stuck matches → error", len(rows))
            await db.commit()

    async def _check_stale_entries(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.debate_queue_timeout_seconds)
        async with async_session() as db:
            # SKIP LOCKED으로 다른 태스크와 충돌 방지
            result = await db.execute(
                select(DebateMatchQueue)
                .where(DebateMatchQueue.joined_at < cutoff)
                .with_for_update(skip_locked=True)
            )
            stale = list(result.scalars().all())

        for entry in stale:
            async with async_session() as db:
                await self._auto_match_with_platform_agent(db, entry)

    async def _auto_match_with_platform_agent(self, db: AsyncSession, entry: DebateMatchQueue) -> None:
        # 엔트리가 아직 큐에 있는지 재확인 (다른 매치로 이미 처리됐을 수 있음)
        fresh = await db.execute(
            select(DebateMatchQueue).where(
                DebateMatchQueue.topic_id == entry.topic_id,
                DebateMatchQueue.agent_id == entry.agent_id,
            )
        )
        if fresh.scalar_one_or_none() is None:
            return

        # 본인 소유가 아닌 활성 플랫폼 에이전트 무작위 선택
        platform_result = await db.execute(
            select(DebateAgent)
            .where(
                DebateAgent.is_platform == True,  # noqa: E712
                DebateAgent.is_active == True,  # noqa: E712
                DebateAgent.owner_id != entry.user_id,
            )
            .order_by(text("random()"))
            .limit(1)
        )
        platform_agent = platform_result.scalar_one_or_none()

        topic_id = str(entry.topic_id)
        agent_id = str(entry.agent_id)

        if platform_agent is None:
            await publish_queue_event(topic_id, agent_id, "timeout", {"reason": "no_platform_agents"})
            logger.warning("No platform agents available for auto-match (topic=%s)", topic_id)
            return

        # 각 에이전트 최신 버전 조회
        ver_user = await self._get_latest_version(db, entry.agent_id)
        ver_platform = await self._get_latest_version(db, platform_agent.id)

        match = DebateMatch(
            topic_id=entry.topic_id,
            agent_a_id=entry.agent_id,
            agent_b_id=platform_agent.id,
            agent_a_version_id=ver_user.id if ver_user else None,
            agent_b_version_id=ver_platform.id if ver_platform else None,
            status="pending",
        )
        db.add(match)

        # 큐 엔트리 제거
        queue_entry = await db.execute(
            select(DebateMatchQueue).where(
                DebateMatchQueue.topic_id == entry.topic_id,
                DebateMatchQueue.agent_id == entry.agent_id,
            )
        )
        entry_obj = queue_entry.scalar_one_or_none()
        if entry_obj:
            await db.delete(entry_obj)

        await db.commit()
        await db.refresh(match)

        match_id = str(match.id)
        platform_id = str(platform_agent.id)
        logger.info("Auto-matched %s with platform agent %s (match=%s)", agent_id, platform_id, match_id)

        # 대기방 SSE에 매칭 이벤트 발행
        await publish_queue_event(topic_id, agent_id, "matched", {
            "match_id": match_id,
            "opponent_agent_id": platform_id,
            "auto_matched": True,
        })

        # 토론 엔진 시작
        asyncio.create_task(run_debate(match_id))

    @staticmethod
    async def _get_latest_version(db: AsyncSession, agent_id) -> DebateAgentVersion | None:
        result = await db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_id)
            .order_by(DebateAgentVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
