"""매칭 서비스. 큐 등록 + 준비 완료 버튼으로 매치 생성. DebateAutoMatcher 포함."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_password
from app.core.config import settings
from app.core.database import async_session
from app.core.exceptions import QueueConflictError
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch, DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.services.debate_agent_service import get_latest_version
from app.services.debate_broadcast import publish_queue_event

logger = logging.getLogger(__name__)


class DebateMatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _purge_expired_entries(self) -> None:
        """만료된 큐 항목 일괄 삭제. join_queue 진입 시 호출."""
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(DebateMatchQueue).where(DebateMatchQueue.expires_at <= now)
        )
        for entry in result.scalars().all():
            await self.db.delete(entry)
        await self.db.flush()

    async def join_queue(self, user: User, topic_id: str, agent_id: str, password: str | None = None) -> dict:
        """큐 등록. 상대가 이미 있으면 양쪽에 opponent_joined 이벤트 발행."""
        # 토픽 검증
        topic = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = topic.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")
        if topic.status != "open":
            raise ValueError("Topic is not open for matches")

        if topic.is_password_protected and (not password or not verify_password(password, topic.password_hash)):
            raise ValueError("비밀번호가 올바르지 않습니다")

        # 에이전트 소유권 검증 (admin/superadmin은 모든 에이전트 사용 가능)
        is_admin = user.role in ("admin", "superadmin")
        if is_admin:
            agent = await self.db.execute(select(DebateAgent).where(DebateAgent.id == agent_id))
        else:
            agent = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
            )
        agent = agent.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found or not owned by user")
        if not agent.is_active:
            raise ValueError("Agent is not active")

        # local 또는 platform credits 사용 에이전트가 아닌 경우 API 키 필수
        if agent.provider != "local" and not agent.use_platform_credits and not agent.encrypted_api_key:
            raise ValueError("Agent has no API key configured")

        await self._purge_expired_entries()

        # 유저당 1개 큐만 허용 (admin 제외)
        if user.role not in ("admin", "superadmin"):
            user_existing = await self.db.execute(
                select(DebateMatchQueue).where(DebateMatchQueue.user_id == user.id)
            )
            existing_user_entry = user_existing.scalar_one_or_none()
            if existing_user_entry is not None:
                raise QueueConflictError(
                    "이미 다른 에이전트로 대기 중입니다. 기존 대기를 취소한 뒤 다시 시도하세요.",
                    str(existing_user_entry.topic_id),
                )

        # 에이전트가 어느 토픽이든 이미 대기 중인지 확인 (에이전트당 1개 토픽 제한)
        existing = await self.db.execute(
            select(DebateMatchQueue).where(
                DebateMatchQueue.agent_id == agent_id,
            )
        )
        existing_entry = existing.scalar_one_or_none()
        if existing_entry is not None:
            if str(existing_entry.topic_id) == str(topic_id):
                raise ValueError("Agent already in queue for this topic")
            raise QueueConflictError(
                "에이전트가 이미 다른 토픽 대기 중입니다. 기존 대기를 취소한 뒤 다시 시도하세요.",
                str(existing_entry.topic_id),
            )

        # 큐 등록
        entry = DebateMatchQueue(
            topic_id=topic_id,
            agent_id=agent_id,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.debate_queue_timeout_seconds),
        )
        self.db.add(entry)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            constraint = str(exc.orig)
            if "uq_debate_queue_topic_agent" in constraint:
                raise ValueError("Agent already in queue for this topic") from exc
            raise ValueError("이미 대기 중인 항목이 있습니다. 잠시 후 다시 시도하세요.") from exc

        # 이미 대기 중인 다른 사용자 확인 (자기 매칭 방지)
        opponent_result = await self.db.execute(
            select(DebateMatchQueue)
            .where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.agent_id != entry.agent_id,
                DebateMatchQueue.user_id != user.id,
            )
            .order_by(DebateMatchQueue.joined_at)
            .limit(1)
        )
        opponent_entry = opponent_result.scalar_one_or_none()

        await self.db.commit()

        if opponent_entry:
            # 상대에게 내가 입장했음을 알림
            await publish_queue_event(topic_id, str(opponent_entry.agent_id), "opponent_joined", {
                "opponent_agent_id": str(agent_id),
            })
            # 나에게도 상대가 있음을 알림
            await publish_queue_event(topic_id, str(agent_id), "opponent_joined", {
                "opponent_agent_id": str(opponent_entry.agent_id),
            })
            return {
                "status": "queued",
                "position": 1,
                "opponent_agent_id": str(opponent_entry.agent_id),
            }

        return {"status": "queued", "position": 1}

    async def ready_up(self, user: User, topic_id: str, agent_id: str) -> dict:
        """준비 완료 처리. 양쪽 모두 준비되면 매치 생성."""
        # 내 큐 엔트리 확인
        my_result = await self.db.execute(
            select(DebateMatchQueue)
            .where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.agent_id == agent_id,
                DebateMatchQueue.user_id == user.id,
            )
            .with_for_update()
        )
        my_entry = my_result.scalar_one_or_none()
        if my_entry is None:
            raise ValueError("Not in queue")

        if my_entry.is_ready:
            return {"status": "already_ready"}

        my_entry.is_ready = True
        await self.db.flush()

        # 상대방 엔트리 조회
        opp_result = await self.db.execute(
            select(DebateMatchQueue)
            .where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.agent_id != agent_id,
                DebateMatchQueue.user_id != user.id,
            )
            .order_by(DebateMatchQueue.joined_at)
            .limit(1)
            .with_for_update()
        )
        opponent_entry = opp_result.scalar_one_or_none()

        if opponent_entry is None:
            await self.db.commit()
            return {"status": "ready", "waiting_for_opponent": True}

        if not opponent_entry.is_ready:
            # 첫 번째 준비 완료 → 10초 카운트다운 시작 이벤트를 양쪽에 발행
            await self.db.commit()
            await publish_queue_event(topic_id, str(my_entry.agent_id), "countdown_started", {
                "countdown_seconds": 10,
                "ready_agent_id": str(my_entry.agent_id),
            })
            await publish_queue_event(topic_id, str(opponent_entry.agent_id), "countdown_started", {
                "countdown_seconds": 10,
                "ready_agent_id": str(my_entry.agent_id),
            })
            return {
                "status": "ready",
                "waiting_for_opponent": False,
                "countdown_started": True,
                "opponent_agent_id": str(opponent_entry.agent_id),
            }

        # 양쪽 모두 준비 완료 → 매치 생성
        ver_a = await get_latest_version(self.db, my_entry.agent_id)
        ver_b = await get_latest_version(self.db, opponent_entry.agent_id)

        match = DebateMatch(
            topic_id=topic_id,
            agent_a_id=my_entry.agent_id,
            agent_b_id=opponent_entry.agent_id,
            agent_a_version_id=ver_a.id if ver_a else None,
            agent_b_version_id=ver_b.id if ver_b else None,
            status="pending",
        )

        # 활성 시즌이 있으면 season_id 태깅
        from app.services.debate_season_service import DebateSeasonService
        season_svc = DebateSeasonService(self.db)
        active_season = await season_svc.get_active_season()
        if active_season:
            match.season_id = active_season.id

        # 시리즈 소속 매치인 경우 match_type / series_id 태깅 (첫 번째 시리즈 기준)
        from app.services.debate_promotion_service import DebatePromotionService
        promo_svc = DebatePromotionService(self.db)
        for agent_id in [str(my_entry.agent_id), str(opponent_entry.agent_id)]:
            series = await promo_svc.get_active_series(agent_id)
            if series:
                match.match_type = series.series_type
                match.series_id = series.id
                break

        self.db.add(match)
        await self.db.delete(my_entry)
        await self.db.delete(opponent_entry)
        await self.db.commit()
        await self.db.refresh(match)

        logger.info("Match created (ready-up): %s (topic=%s)", match.id, topic_id)

        await publish_queue_event(topic_id, str(my_entry.agent_id), "matched", {
            "match_id": str(match.id),
            "opponent_agent_id": str(opponent_entry.agent_id),
            "auto_matched": False,
        })
        await publish_queue_event(topic_id, str(opponent_entry.agent_id), "matched", {
            "match_id": str(match.id),
            "opponent_agent_id": str(my_entry.agent_id),
            "auto_matched": False,
        })

        return {"status": "matched", "match_id": str(match.id)}



# --- DebateAutoMatcher ---


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
        from app.services.debate_engine import run_debate
        asyncio.create_task(run_debate(match_id))
