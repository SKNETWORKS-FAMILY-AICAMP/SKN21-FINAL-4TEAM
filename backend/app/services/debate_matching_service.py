"""매칭 서비스. 큐 등록 + 2명 도달 시 자동 매치 생성."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_match_queue import DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User

logger = logging.getLogger(__name__)


class DebateMatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def join_queue(self, user: User, topic_id: str, agent_id: str) -> dict:
        """큐 등록. 2명 도달 시 자동 매치 생성 후 반환."""
        # 토픽 검증
        topic = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = topic.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")
        if topic.status != "open":
            raise ValueError("Topic is not open for matches")

        # 에이전트 소유권 검증
        agent = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
        )
        agent = agent.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found or not owned by user")
        if not agent.is_active:
            raise ValueError("Agent is not active")

        # local 에이전트가 아닌 경우 API 키 필수
        if agent.provider != "local" and not agent.encrypted_api_key:
            raise ValueError("Agent has no API key configured")

        # 중복 참가 방지
        existing = await self.db.execute(
            select(DebateMatchQueue).where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Agent already in queue for this topic")

        # 큐 등록
        entry = DebateMatchQueue(
            topic_id=topic_id,
            agent_id=agent_id,
            user_id=user.id,
        )
        self.db.add(entry)
        await self.db.flush()

        # 큐에 2명 이상인지 확인 (SELECT ... FOR UPDATE으로 동시성 제어)
        queue_result = await self.db.execute(
            select(DebateMatchQueue)
            .where(DebateMatchQueue.topic_id == topic_id)
            .order_by(DebateMatchQueue.joined_at)
            .with_for_update()
        )
        queue_entries = list(queue_result.scalars().all())

        if len(queue_entries) >= 2:
            entry_a = queue_entries[0]
            entry_b = queue_entries[1]

            # 동일 유저 자기 매칭 방지
            if entry_a.user_id == entry_b.user_id:
                await self.db.commit()
                return {"status": "queued", "position": len(queue_entries)}

            # 각 에이전트의 최신 버전 조회
            ver_a = await self._get_latest_version(entry_a.agent_id)
            ver_b = await self._get_latest_version(entry_b.agent_id)

            match = DebateMatch(
                topic_id=topic_id,
                agent_a_id=entry_a.agent_id,
                agent_b_id=entry_b.agent_id,
                agent_a_version_id=ver_a.id if ver_a else None,
                agent_b_version_id=ver_b.id if ver_b else None,
                status="pending",
            )
            self.db.add(match)

            # 매치된 2명을 큐에서 제거
            await self.db.delete(entry_a)
            await self.db.delete(entry_b)

            await self.db.commit()
            await self.db.refresh(match)

            logger.info("Match created: %s (topic=%s)", match.id, topic_id)
            return {"status": "matched", "match_id": str(match.id)}

        await self.db.commit()
        return {"status": "queued", "position": len(queue_entries)}

    async def _get_latest_version(self, agent_id) -> DebateAgentVersion | None:
        result = await self.db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_id)
            .order_by(DebateAgentVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
