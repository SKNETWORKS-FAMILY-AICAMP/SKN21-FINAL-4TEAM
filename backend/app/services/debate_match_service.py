import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
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
            # 관리자 테스트 매치는 사용자 목록에서 제외 (ELO 미반영 매치)
            .where(DebateMatch.is_test.is_(False))
        )
        count_query = (
            select(func.count(DebateMatch.id))
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .join(DebateAgent, DebateMatch.agent_a_id == DebateAgent.id, isouter=True)
            .where(DebateMatch.is_test.is_(False))
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

    async def create_prediction(self, match_id: str, user_id: uuid.UUID, prediction: str) -> dict:
        """예측 투표. status='in_progress' && turn_count<=2만 허용."""
        from app.models.debate_match_prediction import DebateMatchPrediction

        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError("Match not found")
        if match.status != "in_progress":
            raise ValueError("투표는 진행 중인 매치에서만 가능합니다")

        # turn_count 조회
        cnt_result = await self.db.execute(
            select(func.count(DebateTurnLog.id)).where(DebateTurnLog.match_id == match.id)
        )
        turn_count = cnt_result.scalar() or 0
        if turn_count > 2:
            raise ValueError("투표 시간이 지났습니다 (2턴 이후 불가)")

        # 중복 검사
        dup = await self.db.execute(
            select(DebateMatchPrediction).where(
                DebateMatchPrediction.match_id == match.id,
                DebateMatchPrediction.user_id == user_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ValueError("DUPLICATE")

        pred = DebateMatchPrediction(match_id=match.id, user_id=user_id, prediction=prediction)
        self.db.add(pred)
        await self.db.commit()
        return {"ok": True, "prediction": prediction}

    async def get_prediction_stats(self, match_id: str, user_id: uuid.UUID) -> dict:
        """집계 + 내 투표 결과 반환."""
        from app.models.debate_match_prediction import DebateMatchPrediction

        agg = await self.db.execute(
            select(
                func.sum(sa_case((DebateMatchPrediction.prediction == "a_win", 1), else_=0)).label("a_win"),
                func.sum(sa_case((DebateMatchPrediction.prediction == "b_win", 1), else_=0)).label("b_win"),
                func.sum(sa_case((DebateMatchPrediction.prediction == "draw", 1), else_=0)).label("draw"),
                func.count().label("total"),
            ).where(DebateMatchPrediction.match_id == match_id)
        )
        row = agg.one()

        my = await self.db.execute(
            select(DebateMatchPrediction).where(
                DebateMatchPrediction.match_id == match_id,
                DebateMatchPrediction.user_id == user_id,
            )
        )
        my_pred = my.scalar_one_or_none()

        return {
            "a_win": int(row.a_win or 0),
            "b_win": int(row.b_win or 0),
            "draw": int(row.draw or 0),
            "total": int(row.total or 0),
            "my_prediction": my_pred.prediction if my_pred else None,
            "is_correct": my_pred.is_correct if my_pred else None,
        }

    async def resolve_predictions(
        self, match_id: str, winner_id: str | None, agent_a_id: str, agent_b_id: str
    ) -> None:
        """판정 후 is_correct 업데이트."""
        from app.models.debate_match_prediction import DebateMatchPrediction

        if winner_id is None:
            correct_pred = "draw"
        elif str(winner_id) == str(agent_a_id):
            correct_pred = "a_win"
        else:
            correct_pred = "b_win"

        await self.db.execute(
            sa_update(DebateMatchPrediction)
            .where(DebateMatchPrediction.match_id == match_id)
            .values(is_correct=(DebateMatchPrediction.prediction == correct_pred))
        )
        await self.db.commit()

    async def toggle_featured(self, match_id: str, featured: bool) -> dict:
        """관리자 전용. 미완료 매치는 400."""
        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError("Match not found")
        if match.status != "completed":
            raise ValueError("완료된 매치만 하이라이트로 설정 가능합니다")

        await self.db.execute(
            sa_update(DebateMatch)
            .where(DebateMatch.id == match_id)
            .values(
                is_featured=featured,
                featured_at=datetime.now(UTC) if featured else None,
            )
        )
        await self.db.commit()
        return {"ok": True, "is_featured": featured}

    async def list_featured(self, limit: int = 5) -> tuple[list[dict], int]:
        """is_featured=True, featured_at DESC."""
        q = (
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(DebateMatch.is_featured == True)  # noqa: E712
            .order_by(DebateMatch.featured_at.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(q)).all()

        agent_ids = {
            id_
            for match, _ in rows
            for id_ in (match.agent_a_id, match.agent_b_id)
            if id_ is not None
        }
        agents_map: dict = {}
        if agent_ids:
            res = await self.db.execute(select(DebateAgent).where(DebateAgent.id.in_(agent_ids)))
            agents_map = {str(a.id): a for a in res.scalars()}

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
                "is_featured": match.is_featured,
                "featured_at": match.featured_at,
                "started_at": match.started_at,
                "finished_at": match.finished_at,
                "created_at": match.created_at,
            })
        return items, len(items)
