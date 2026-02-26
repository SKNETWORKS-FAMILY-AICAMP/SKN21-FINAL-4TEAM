import logging
from datetime import datetime

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
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[list[dict], int]:
        query = (
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .join(DebateAgent, DebateMatch.agent_a_id == DebateAgent.id, isouter=True)
        )
        count_query = (
            select(func.count(DebateMatch.id))
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .join(DebateAgent, DebateMatch.agent_a_id == DebateAgent.id, isouter=True)
        )

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
        if search:
            # 에이전트명(A측) 또는 토픽 제목으로 검색
            like = f"%{search}%"
            search_cond = (DebateAgent.name.ilike(like)) | (DebateTopic.title.ilike(like))
            query = query.where(search_cond)
            count_query = count_query.where(search_cond)
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                query = query.where(DebateMatch.created_at >= dt_from)
                count_query = count_query.where(DebateMatch.created_at >= dt_from)
            except ValueError:
                logger.warning("list_matches: invalid date_from=%s, skipping", date_from)
        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to)
                query = query.where(DebateMatch.created_at <= dt_to)
                count_query = count_query.where(DebateMatch.created_at <= dt_to)
            except ValueError:
                logger.warning("list_matches: invalid date_to=%s, skipping", date_to)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(DebateMatch.created_at.desc()).offset(skip).limit(limit)
        )
        rows = result.all()

        # N+1 방지: 페이지 내 모든 에이전트 ID를 단일 배치 쿼리로 조회
        agent_ids = {
            id_
            for match, _ in rows
            for id_ in (match.agent_a_id, match.agent_b_id)
            if id_ is not None
        }
        agents_map: dict = {}
        if agent_ids:
            agents_result = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id.in_(agent_ids))
            )
            agents_map = {str(a.id): a for a in agents_result.scalars()}

        items = []
        for match, topic_title in rows:
            agent_a = self._agent_from_map(agents_map, match.agent_a_id)
            agent_b = self._agent_from_map(agents_map, match.agent_b_id)
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

    def _agent_from_map(self, agents_map: dict, agent_id) -> dict:
        """배치 조회된 agents_map에서 에이전트 요약 반환."""
        if agent_id is None:
            return {"id": None, "name": "[없음]", "provider": "", "model_id": "", "elo_rating": 0, "image_url": None}
        a = agents_map.get(str(agent_id))
        if a is None:
            return {"id": str(agent_id), "name": "[삭제됨]", "provider": "", "model_id": "", "elo_rating": 0, "image_url": None}
        return {
            "id": str(a.id),
            "name": a.name,
            "provider": a.provider,
            "model_id": a.model_id,
            "elo_rating": a.elo_rating,
            "image_url": a.image_url,
        }

    async def _get_agent_summary(self, agent_id) -> dict:
        """단일 에이전트 조회. get_match 등 단건 조회에 사용."""
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            return {
                "id": str(agent_id), "name": "[삭제됨]",
                "provider": "", "model_id": "", "elo_rating": 0, "image_url": None,
            }
        return {
            "id": str(agent.id),
            "name": agent.name,
            "provider": agent.provider,
            "model_id": agent.model_id,
            "elo_rating": agent.elo_rating,
            "image_url": agent.image_url,
        }
