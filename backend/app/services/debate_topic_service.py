import logging
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_match import DebateMatch
from app.models.debate_match_queue import DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.schemas.debate_topic import TopicCreate, TopicUpdate

logger = logging.getLogger(__name__)


class DebateTopicService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_topic(self, data: TopicCreate, user: User) -> DebateTopic:
        """토론 주제 생성. 관리자는 스케줄 설정 가능, 일반 유저는 즉시 open."""
        is_admin = user.role in ("admin", "superadmin")
        now = datetime.now(UTC)

        # 시작 시각이 미래이면 scheduled, 아니면 open
        initial_status = "scheduled" if data.scheduled_start_at and data.scheduled_start_at > now else "open"

        topic = DebateTopic(
            title=data.title,
            description=data.description,
            mode=data.mode,
            max_turns=data.max_turns,
            turn_token_limit=data.turn_token_limit,
            tools_enabled=data.tools_enabled,
            scheduled_start_at=data.scheduled_start_at if is_admin else None,
            scheduled_end_at=data.scheduled_end_at if is_admin else None,
            is_admin_topic=is_admin,
            status=initial_status,
            created_by=user.id,
        )
        self.db.add(topic)
        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    async def get_topic(self, topic_id: str) -> DebateTopic | None:
        result = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def list_topics(
        self, status: str | None = None, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """토픽 목록 조회. 조회 전 스케줄 상태 자동 동기화."""
        await self._sync_scheduled_topics()

        query = select(DebateTopic)
        count_query = select(func.count(DebateTopic.id))

        if status:
            query = query.where(DebateTopic.status == status)
            count_query = count_query.where(DebateTopic.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(DebateTopic.created_at.desc()).offset(skip).limit(limit)
        )
        topics = list(result.scalars().all())

        items = []
        for topic in topics:
            queue_count = await self._count_queue(topic.id)
            match_count = await self._count_matches(topic.id)
            items.append({
                "id": str(topic.id),
                "title": topic.title,
                "description": topic.description,
                "mode": topic.mode,
                "status": topic.status,
                "max_turns": topic.max_turns,
                "turn_token_limit": topic.turn_token_limit,
                "scheduled_start_at": topic.scheduled_start_at,
                "scheduled_end_at": topic.scheduled_end_at,
                "is_admin_topic": topic.is_admin_topic,
                "tools_enabled": topic.tools_enabled,
                "queue_count": queue_count,
                "match_count": match_count,
                "created_at": topic.created_at,
                "updated_at": topic.updated_at,
            })

        return items, total

    async def update_topic(self, topic_id: str, data: TopicUpdate) -> DebateTopic:
        result = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(topic, field, value)

        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    async def delete_topic(self, topic_id: str) -> None:
        """토픽 삭제 (매치가 없는 경우만 허용). 대기 큐를 먼저 정리."""
        from sqlalchemy import delete as sa_delete

        result = await self.db.execute(
            select(DebateTopic).where(DebateTopic.id == topic_id)
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            raise ValueError("Topic not found")

        match_count = await self._count_matches(topic.id)
        if match_count > 0:
            raise ValueError(
                f"진행된 매치가 {match_count}개 있어 삭제할 수 없습니다. "
                "종료 처리 후 매치가 없을 때 삭제 가능합니다."
            )

        # 대기 큐 먼저 제거
        await self.db.execute(
            sa_delete(DebateMatchQueue).where(DebateMatchQueue.topic_id == topic.id)
        )
        await self.db.delete(topic)
        await self.db.commit()

    async def _sync_scheduled_topics(self) -> None:
        """scheduled_start_at/end_at 기준으로 status 자동 갱신."""
        now = datetime.now(UTC)

        # scheduled → open (시작 시각 도달)
        await self.db.execute(
            update(DebateTopic)
            .where(
                DebateTopic.status == "scheduled",
                DebateTopic.scheduled_start_at <= now,
            )
            .values(status="open")
        )

        # open/in_progress → closed (종료 시각 초과)
        await self.db.execute(
            update(DebateTopic)
            .where(
                DebateTopic.status.in_(["open", "in_progress"]),
                DebateTopic.scheduled_end_at.isnot(None),
                DebateTopic.scheduled_end_at <= now,
            )
            .values(status="closed")
        )

        await self.db.commit()

    async def _count_queue(self, topic_id) -> int:
        result = await self.db.execute(
            select(func.count(DebateMatchQueue.id)).where(DebateMatchQueue.topic_id == topic_id)
        )
        return result.scalar() or 0

    async def _count_matches(self, topic_id) -> int:
        result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(DebateMatch.topic_id == topic_id)
        )
        return result.scalar() or 0
