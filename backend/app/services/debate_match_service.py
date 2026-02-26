import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog

logger = logging.getLogger(__name__)


class DebateMatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_match(self, match_id: str) -> dict | None:
        """매치 상세 조회. 에이전트 요약 포함."""
        result = await self.db.execute(
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(DebateMatch.id == match_id)
        )
        row = result.one_or_none()
        if row is None:
            return None

        match, topic_title = row

        agent_a = await self._get_agent_summary(match.agent_a_id)
        agent_b = await self._get_agent_summary(match.agent_b_id)

        turn_count_result = await self.db.execute(
            select(func.count(DebateTurnLog.id)).where(DebateTurnLog.match_id == match.id)
        )
        turn_count = turn_count_result.scalar() or 0

        return {
            "id": str(match.id),
            "topic_id": str(match.topic_id),
            "topic_title": topic_title,
            "agent_a": agent_a,
            "agent_b": agent_b,
            "status": match.status,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "score_a": match.score_a,
            "score_b": match.score_b,
            "penalty_a": match.penalty_a,
            "penalty_b": match.penalty_b,
            "turn_count": turn_count,
            "started_at": match.started_at,
            "finished_at": match.finished_at,
            "created_at": match.created_at,
        }

    async def get_match_turns(self, match_id: str) -> list[DebateTurnLog]:
        result = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match_id)
            .order_by(DebateTurnLog.turn_number)
        )
        return list(result.scalars().all())

    async def get_scorecard(self, match_id: str) -> dict | None:
        result = await self.db.execute(
            select(DebateMatch).where(DebateMatch.id == match_id)
        )
        match = result.scalar_one_or_none()
        if match is None or match.scorecard is None:
            return None
        return {
            **match.scorecard,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "result": "draw" if match.winner_id is None and match.status == "completed" else (
                "win" if match.winner_id else "pending"
            ),
        }

    async def list_matches(
        self,
        topic_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        query = select(DebateMatch, DebateTopic.title).join(
            DebateTopic, DebateMatch.topic_id == DebateTopic.id
        )
        count_query = select(func.count(DebateMatch.id))

        if topic_id:
            query = query.where(DebateMatch.topic_id == topic_id)
            count_query = count_query.where(DebateMatch.topic_id == topic_id)
        if agent_id:
            query = query.where(
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id)
            )
            count_query = count_query.where(
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id)
            )
        if status:
            query = query.where(DebateMatch.status == status)
            count_query = count_query.where(DebateMatch.status == status)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(DebateMatch.created_at.desc()).offset(skip).limit(limit)
        )
        rows = result.all()

        items = []
        for match, topic_title in rows:
            agent_a = await self._get_agent_summary(match.agent_a_id)
            agent_b = await self._get_agent_summary(match.agent_b_id)
            items.append({
                "id": str(match.id),
                "topic_id": str(match.topic_id),
                "topic_title": topic_title,
                "agent_a": agent_a,
                "agent_b": agent_b,
                "status": match.status,
                "winner_id": str(match.winner_id) if match.winner_id else None,
                "score_a": match.score_a,
                "score_b": match.score_b,
                "penalty_a": match.penalty_a,
                "penalty_b": match.penalty_b,
                "started_at": match.started_at,
                "finished_at": match.finished_at,
                "created_at": match.created_at,
            })

        return items, total

    async def _get_agent_summary(self, agent_id) -> dict:
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            return {"id": str(agent_id), "name": "[삭제됨]", "provider": "", "model_id": "", "elo_rating": 0, "image_url": None}
        return {
            "id": str(agent.id),
            "name": agent.name,
            "provider": agent.provider,
            "model_id": agent.model_id,
            "elo_rating": agent.elo_rating,
            "image_url": agent.image_url,
        }
