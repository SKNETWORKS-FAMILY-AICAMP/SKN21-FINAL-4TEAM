"""매칭 서비스. 큐 등록 + 준비 완료 버튼으로 매치 생성."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_password
from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_match_queue import DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.services.debate_queue_broadcast import publish_queue_event

logger = logging.getLogger(__name__)


class DebateMatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

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

        # 유저당 1개 큐만 허용 (admin 제외)
        if user.role not in ("admin", "superadmin"):
            user_existing = await self.db.execute(
                select(DebateMatchQueue).where(DebateMatchQueue.user_id == user.id)
            )
            if user_existing.scalar_one_or_none() is not None:
                raise ValueError("이미 다른 에이전트로 대기 중입니다. 기존 대기를 취소한 뒤 다시 시도하세요.")

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
            raise ValueError("Agent is already waiting in another topic queue. Leave that queue first.")

        # 큐 등록
        entry = DebateMatchQueue(
            topic_id=topic_id,
            agent_id=agent_id,
            user_id=user.id,
        )
        self.db.add(entry)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            constraint = str(exc.orig)
            if "uq_debate_queue_topic_agent" in constraint:
                raise ValueError("Agent already in queue for this topic")
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
        ver_a = await self._get_latest_version(my_entry.agent_id)
        ver_b = await self._get_latest_version(opponent_entry.agent_id)

        match = DebateMatch(
            topic_id=topic_id,
            agent_a_id=my_entry.agent_id,
            agent_b_id=opponent_entry.agent_id,
            agent_a_version_id=ver_a.id if ver_a else None,
            agent_b_version_id=ver_b.id if ver_b else None,
            status="pending",
        )

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

    async def _get_latest_version(self, agent_id) -> DebateAgentVersion | None:
        result = await self.db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_id)
            .order_by(DebateAgentVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
