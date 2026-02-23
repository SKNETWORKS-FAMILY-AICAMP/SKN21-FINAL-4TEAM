import logging

from sqlalchemy import func, select
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
        """관리자가 토론 주제 생성."""
        topic = DebateTopic(
            title=data.title,
            description=data.description,
            mode=data.mode,
            max_turns=data.max_turns,
            turn_token_limit=data.turn_token_limit,
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
        """토픽 목록 조회. 큐 인원/매치 수 포함."""
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

        if data.title is not None:
            topic.title = data.title
        if data.description is not None:
            topic.description = data.description
        if data.status is not None:
            topic.status = data.status
        if data.max_turns is not None:
            topic.max_turns = data.max_turns
        if data.turn_token_limit is not None:
            topic.turn_token_limit = data.turn_token_limit

        await self.db.commit()
        await self.db.refresh(topic)
        return topic

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
