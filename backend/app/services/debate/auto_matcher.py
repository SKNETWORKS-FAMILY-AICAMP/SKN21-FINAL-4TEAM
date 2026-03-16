"""자동 매칭 데몬. 백그라운드 루프에서 큐 만료·stuck 매치·자동 매칭을 처리한다."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch, DebateMatchQueue
from app.services.debate.agent_service import get_latest_version
from app.services.debate.broadcast import publish_queue_event
from app.services.debate.engine import run_debate

logger = logging.getLogger(__name__)


class DebateAutoMatcher:
    """싱글톤 자동 매칭 태스크. 백그라운드 루프에서 주기적으로 큐 상태를 점검한다.

    역할:
      - 만료된 큐 항목 정리 (_purge_expired_queue_entries)
      - 장시간 대기 큐 항목을 플랫폼 에이전트와 자동 매칭 (_check_stale_entries)
      - pending/waiting_agent 상태로 멈춘 매치를 error로 처리 (_check_stuck_matches)

    점검 주기: settings.debate_auto_match_check_interval (초)
    서버 시작 시 lifespan에서 start() 호출, 종료 시 stop() 호출.
    """

    _instance = None

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> "DebateAutoMatcher":
        """싱글톤 인스턴스를 반환한다. 없으면 생성 후 반환.

        Returns:
            DebateAutoMatcher 싱글톤 인스턴스.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        """자동 매칭 백그라운드 루프를 시작한다.

        FastAPI lifespan에서 호출. 이미 실행 중이면 무시한다.
        """
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("DebateAutoMatcher started")

    def stop(self) -> None:
        """자동 매칭 루프를 중지한다. FastAPI lifespan 종료 시 호출."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("DebateAutoMatcher stopped")

    async def _loop(self) -> None:
        """자동 매칭 백그라운드 루프 본체.

        서버 시작 직후 한 번 즉시 정리 후, debate_auto_match_check_interval 주기로 반복.
        각 이터레이션에서 만료 큐 정리 → 장기 대기 자동 매칭 → stuck 매치 처리 순으로 실행한다.
        """
        # 시작 직후 한 번 즉시 정리 (서버 재시작 후 잔류 상태 초기화)
        try:
            await self._purge_expired_queue_entries()
            await self._check_stale_entries()
            await self._check_stuck_matches()
        except Exception:
            logger.exception("DebateAutoMatcher startup cleanup error")

        while self._running:
            try:
                await self._purge_expired_queue_entries()
                await self._check_stale_entries()
                await self._check_stuck_matches()
            except Exception:
                logger.exception("DebateAutoMatcher loop error")
            await asyncio.sleep(settings.debate_auto_match_check_interval)

    async def _check_stuck_matches(self) -> None:
        """장시간 멈춘 매치를 error로 처리.

        - pending/waiting_agent: created_at 기준 debate_pending_timeout_seconds 초과
        - in_progress: started_at 기준 debate_inprogress_timeout_seconds 초과 (서버 비정상 종료 대비)
        """
        now = datetime.now(UTC)
        pending_cutoff = now - timedelta(seconds=settings.debate_pending_timeout_seconds)
        inprogress_cutoff = now - timedelta(seconds=settings.debate_inprogress_timeout_seconds)

        async with async_session() as db:
            result = await db.execute(
                update(DebateMatch)
                .where(
                    DebateMatch.status.in_(["pending", "waiting_agent"]),
                    DebateMatch.created_at < pending_cutoff,
                )
                .values(status="error")
                .returning(DebateMatch.id)
            )
            pending_rows = result.fetchall()

            result = await db.execute(
                update(DebateMatch)
                .where(
                    DebateMatch.status == "in_progress",
                    DebateMatch.started_at < inprogress_cutoff,
                )
                .values(status="error", finished_at=now)
                .returning(DebateMatch.id)
            )
            inprogress_rows = result.fetchall()

            if pending_rows:
                logger.warning("Cleaned up %d stuck matches (pending/waiting_agent) → error", len(pending_rows))
            if inprogress_rows:
                logger.warning("Cleaned up %d stuck matches (in_progress) → error", len(inprogress_rows))

            await db.commit()

    async def _purge_expired_queue_entries(self) -> None:
        """만료된 큐 항목 삭제 + timeout SSE 발행. _loop()에서 주기 호출."""
        now = datetime.now(UTC)
        async with async_session() as db:
            result = await db.execute(
                select(DebateMatchQueue)
                .where(DebateMatchQueue.expires_at <= now)
                .with_for_update(skip_locked=True)
            )
            expired = result.scalars().all()
            for entry in expired:
                await db.delete(entry)
                await publish_queue_event(
                    str(entry.topic_id), str(entry.agent_id), "timeout", {"reason": "queue_expired"}
                )
            if expired:
                logger.info("Purged %d expired queue entries", len(expired))
            await db.commit()

    async def _check_stale_entries(self) -> None:
        """debate_queue_timeout_seconds를 초과한 큐 항목을 플랫폼 에이전트와 자동 매칭.

        사용자가 ready_up 버튼을 누르지 않고 장시간 대기한 경우를 처리.
        플랫폼 에이전트가 없으면 timeout 이벤트 발행 후 포기.
        """
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
        """큐 항목을 무작위 플랫폼 에이전트와 매칭하고 토론 엔진을 시작한다.

        is_platform=True인 에이전트 중 entry.user_id 소유가 아닌 것을 random()으로 선택.
        매칭 후 큐 항목 삭제 → DebateMatch 생성 → run_debate 백그라운드 태스크 실행.
        """
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
        ver_user = await get_latest_version(db, entry.agent_id)
        ver_platform = await get_latest_version(db, platform_agent.id)

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
