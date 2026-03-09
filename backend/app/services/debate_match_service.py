import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog

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
        include_test: bool = False,
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
        if not include_test:
            # 테스트 매치(관리자 강제매치)는 일반 목록에서 제외 — ELO 미반영
            query = query.where(DebateMatch.is_test.is_(False))
            count_query = count_query.where(DebateMatch.is_test.is_(False))

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
            return {
                "id": str(agent_id), "name": "[삭제됨]",
                "provider": "", "model_id": "", "elo_rating": 0, "image_url": None,
            }
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
        from app.models.debate_match import DebateMatchPrediction

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
        from app.models.debate_match import DebateMatchPrediction

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
        from app.models.debate_match import DebateMatchPrediction

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
        featured_cond = DebateMatch.is_featured == True  # noqa: E712

        total_result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(featured_cond)
        )
        total = total_result.scalar() or 0

        q = (
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(featured_cond)
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
        return items, total


# --- DebateSummaryService ---

SUMMARY_SYSTEM_PROMPT = """당신은 AI 토론 분석 전문가입니다. 토론 로그를 분석하여 JSON 형식으로 요약을 생성하세요.

반드시 다음 JSON 형식으로만 응답하세요:
{
  "key_arguments": ["핵심 논거 1", "핵심 논거 2", "핵심 논거 3"],
  "winning_points": ["승부 포인트 1", "승부 포인트 2"],
  "rule_violations": ["위반 사항 1"],
  "overall_summary": "전체 토론 요약 (3-4문장)"
}"""


def _format_summary_log(turns: list, agent_a_name: str, agent_b_name: str) -> str:
    """턴 로그를 텍스트로 포맷."""
    name_map = {"agent_a": agent_a_name, "agent_b": agent_b_name}
    lines = []
    for t in turns:
        speaker_name = name_map.get(t.speaker, t.speaker)
        lines.append(f"[{speaker_name} 턴 {t.turn_number}] {t.action}: {t.claim}")
        if t.evidence:
            lines.append(f"  근거: {t.evidence}")
        if t.penalty_total > 0:
            lines.append(f"  벌점: {t.penalty_total}")
    return "\n".join(lines)


class DebateSummaryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_summary(self, match_id: str) -> None:
        """매치 완료 후 비동기 호출. 이미 summary_report가 있으면 스킵."""
        from app.core.config import settings

        res = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = res.scalar_one_or_none()
        if match is None or match.status != "completed":
            return
        if match.summary_report is not None:
            return  # 중복 방지

        # 에이전트 이름 조회
        agents_res = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
        )
        agents = {str(a.id): a.name for a in agents_res.scalars().all()}
        agent_a_name = agents.get(str(match.agent_a_id), "Agent A")
        agent_b_name = agents.get(str(match.agent_b_id), "Agent B")

        # 턴 로그 조회
        turns_res = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match.id)
            .order_by(DebateTurnLog.turn_number)
        )
        turns = list(turns_res.scalars().all())
        if not turns:
            return

        log_text = _format_summary_log(turns, agent_a_name, agent_b_name)

        try:
            from app.services.inference_client import InferenceClient

            # llm_models 테이블에서 요약 모델 조회 — Langfuse 추적 및 토큰 로그 기록에 필요
            model_res = await self.db.execute(
                select(LLMModel).where(LLMModel.model_id == settings.debate_summary_model)
            )
            llm_model = model_res.scalar_one_or_none()
            if llm_model is None:
                logger.warning(
                    "Summary skipped for match %s: model '%s' not found in llm_models",
                    match_id,
                    settings.debate_summary_model,
                )
                return

            messages = [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"참가자: {agent_a_name} vs {agent_b_name}\n\n"
                        f"다음 토론 로그를 분석하세요:\n\n{log_text[:4000]}"
                    ),
                },
            ]

            client = InferenceClient()
            result = await client.generate(
                model=llm_model,
                messages=messages,
                max_tokens=800,
                temperature=0.3,
            )

            parsed = json.loads(result["content"])
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)

            # 토큰 사용량 기록 — agent_a 소유자를 사용량 귀속 대상으로 지정
            agent_res = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id == match.agent_a_id)
            )
            agent_a_obj = agent_res.scalar_one_or_none()
            if agent_a_obj is not None and (input_tokens > 0 or output_tokens > 0):
                input_cost = (
                    Decimal(str(input_tokens))
                    * Decimal(str(llm_model.input_cost_per_1m))
                    / Decimal("1000000")
                )
                output_cost = (
                    Decimal(str(output_tokens))
                    * Decimal(str(llm_model.output_cost_per_1m))
                    / Decimal("1000000")
                )
                self.db.add(TokenUsageLog(
                    user_id=agent_a_obj.owner_id,
                    session_id=None,
                    llm_model_id=llm_model.id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=input_cost + output_cost,
                ))

            summary_report = {
                "key_arguments": parsed.get("key_arguments", []),
                "winning_points": parsed.get("winning_points", []),
                "rule_violations": parsed.get("rule_violations", []),
                "overall_summary": parsed.get("overall_summary", ""),
                "generated_at": datetime.now(UTC).isoformat(),
                "model_used": settings.debate_summary_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            await self.db.execute(
                sa_update(DebateMatch)
                .where(DebateMatch.id == match.id)
                .values(summary_report=summary_report)
            )
            await self.db.commit()
            logger.info("Summary generated for match %s", match_id)

        except Exception as exc:
            logger.warning("Summary generation failed for match %s: %s", match_id, exc)


async def generate_summary_task(match_id: str) -> None:
    """백그라운드 태스크용 — 독립 DB 세션 생성."""
    from app.core.config import settings

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        service = DebateSummaryService(db)
        await service.generate_summary(match_id)
    await engine.dispose()
