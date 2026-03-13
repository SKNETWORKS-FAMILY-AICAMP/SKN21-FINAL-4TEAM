"""토론 엔진. 비동기 백그라운드 태스크로 매치를 실행."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User
from app.schemas.debate_ws import WSMatchReady
from app.services.debate.broadcast import publish_event
from app.services.debate.finalizer import MatchFinalizer
from app.services.debate.forfeit import ForfeitError, ForfeitHandler
from app.services.debate.formats import (
    TurnLoopResult,
    _apply_review_to_turn,
    _log_orchestrator_usage,
    _publish_review_event,
    _publish_turn_event,
    get_format_runner,
    run_turns_1v1,
    run_turns_multi,
)
from app.services.debate.helpers import (
    _build_messages,
    _resolve_api_key,
    calculate_elo,
    detect_repetition,
    validate_response_schema,
    RESPONSE_SCHEMA_INSTRUCTION,
)
from app.services.debate.orchestrator import DebateOrchestrator
from app.services.debate.turn_executor import TurnExecutor
from app.services.debate.ws_manager import WSConnectionManager
from app.services.llm.inference_client import InferenceClient

logger = logging.getLogger(__name__)

# 상단 import로 sub-module 심볼을 이 네임스페이스에 바인딩 — 테스트 import 경로 보호
# (from app.services.debate.engine import _resolve_api_key 등이 계속 동작)
__all__ = ["run_debate", "DebateEngine"]


# ── 테스트 하위 호환 래퍼 ──────────────────────────────────────────────────────
# 기존 테스트가 engine 모듈에서 직접 import하는 경로를 유지한다.
# 향후 테스트를 turn_executor / formats 모듈 경로로 마이그레이션하면 제거 가능.

async def _execute_turn_with_retry(
    db: AsyncSession,
    client: InferenceClient,
    match: DebateMatch,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    agent: DebateAgent,
    version: DebateAgentVersion | None,
    api_key: str,
    my_claims: list[str],
    opponent_claims: list[str],
    my_accumulated_penalty: int = 0,
) -> DebateTurnLog | None:
    """TurnExecutor.execute_with_retry 래퍼 — 테스트 import 경로 유지."""
    executor = TurnExecutor(client, db)
    return await executor.execute_with_retry(
        match, topic, turn_number, speaker,
        agent, version, api_key, my_claims, opponent_claims,
        my_accumulated_penalty=my_accumulated_penalty,
    )


# 하위 호환 래퍼 — formats.run_turns_1v1로 마이그레이션 후 제거 예정

async def _run_turn_loop(
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    key_a: str,
    key_b: str,
    client: InferenceClient,
    orchestrator: DebateOrchestrator,
    model_cache: dict,
    usage_batch: list,
    parallel: bool,
) -> tuple[list[str], list[str], int, int]:
    """formats.run_turns_1v1 위임 래퍼 — 테스트 import 경로 유지."""
    executor = TurnExecutor(client, db)
    result = await run_turns_1v1(
        executor, orchestrator, db, match, topic,
        agent_a, agent_b, version_a, version_b, key_a, key_b,
        model_cache, usage_batch, parallel,
    )
    return result.claims_a, result.claims_b, result.total_penalty_a, result.total_penalty_b


# ── DebateEngine 클래스 ────────────────────────────────────────────────────────

class DebateEngine:
    """매치 실행 오케스트레이터 — 엔티티 로드 + 포맷 dispatch + finalize."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run(self, match_id: str) -> None:
        """진입점. 엔티티 로드 → 로컬 에이전트 대기 → 크레딧 차감 → 포맷 runner → 판정 → 후처리."""
        match, topic, agent_a, agent_b, version_a, version_b = await self._load_entities(match_id)
        await self._wait_for_local_agents(match, topic, agent_a, agent_b)

        if match.status == "forfeited":
            # 로컬 에이전트 접속 실패로 몰수패 처리된 경우
            return

        await self._deduct_credits(match, agent_a, agent_b)

        use_platform = getattr(match, "is_test", False)
        key_a = _resolve_api_key(agent_a, force_platform=use_platform)
        key_b = _resolve_api_key(agent_b, force_platform=use_platform)

        match.status = "in_progress"
        match.started_at = datetime.now(UTC)
        await self.db.commit()
        await publish_event(str(match.id), "started", {"match_id": str(match.id)})

        async with InferenceClient() as client:
            await self._run_with_client(
                client, match, topic, agent_a, agent_b, version_a, version_b, key_a, key_b
            )

    async def _load_entities(
        self, match_id: str
    ) -> tuple[DebateMatch, DebateTopic, DebateAgent, DebateAgent, DebateAgentVersion | None, DebateAgentVersion | None]:
        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError(f"Match {match_id} not found")

        topic_result = await self.db.execute(select(DebateTopic).where(DebateTopic.id == match.topic_id))
        topic = topic_result.scalar_one()

        agents_res = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
        )
        agents_map = {str(a.id): a for a in agents_res.scalars().all()}
        agent_a = agents_map[str(match.agent_a_id)]
        agent_b = agents_map[str(match.agent_b_id)]

        version_ids = [v for v in [match.agent_a_version_id, match.agent_b_version_id] if v is not None]
        versions_map: dict = {}
        if version_ids:
            versions_res = await self.db.execute(
                select(DebateAgentVersion).where(DebateAgentVersion.id.in_(version_ids))
            )
            versions_map = {str(v.id): v for v in versions_res.scalars().all()}
        version_a = versions_map.get(str(match.agent_a_version_id)) if match.agent_a_version_id else None
        version_b = versions_map.get(str(match.agent_b_version_id)) if match.agent_b_version_id else None

        return match, topic, agent_a, agent_b, version_a, version_b

    async def _wait_for_local_agents(
        self,
        match: DebateMatch,
        topic: DebateTopic,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
    ) -> None:
        ws_manager = WSConnectionManager.get_instance()
        has_local = agent_a.provider == "local" or agent_b.provider == "local"
        if not has_local:
            return

        match.status = "waiting_agent"
        await self.db.commit()
        await publish_event(str(match.id), "waiting_agent", {"match_id": str(match.id)})

        for agent, side in [(agent_a, "agent_a"), (agent_b, "agent_b")]:
            if agent.provider == "local":
                connected = await ws_manager.wait_for_connection(
                    agent.id, settings.debate_agent_connect_timeout
                )
                if not connected:
                    winner_agent = agent_b if side == "agent_a" else agent_a
                    await ForfeitHandler(self.db).handle_disconnect(match, agent, winner_agent, side)
                    match.status = "forfeited"
                    return

        # 모든 로컬 에이전트 접속 완료 — match_ready 전송
        for agent, side in [(agent_a, "agent_a"), (agent_b, "agent_b")]:
            if agent.provider == "local":
                opponent = agent_b if side == "agent_a" else agent_a
                await ws_manager.send_match_ready(agent.id, WSMatchReady(
                    match_id=match.id,
                    topic_title=topic.title,
                    opponent_name=opponent.name,
                    your_side=side,
                ))

    async def _deduct_credits(
        self,
        match: DebateMatch,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
    ) -> None:
        """BYOK가 아닌 에이전트 소유자의 크레딧 차감."""
        if not (settings.debate_credit_cost > 0 and settings.credit_system_enabled):
            return

        for agent in (agent_a, agent_b):
            if agent.encrypted_api_key:
                continue
            deduct_result = await self.db.execute(
                update(User)
                .where(User.id == agent.owner_id, User.credit_balance >= settings.debate_credit_cost)
                .values(credit_balance=User.credit_balance - settings.debate_credit_cost)
                .returning(User.credit_balance)
            )
            if deduct_result.fetchone() is None:
                raise ValueError(
                    f"에이전트 '{agent.name}' 소유자의 크레딧이 부족합니다 (필요: {settings.debate_credit_cost}석)"
                )

        await self.db.commit()

    async def _run_with_client(
        self,
        client: InferenceClient,
        match: DebateMatch,
        topic: DebateTopic,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        version_a: DebateAgentVersion | None,
        version_b: DebateAgentVersion | None,
        key_a: str,
        key_b: str,
    ) -> None:
        """InferenceClient 준비 후 포맷 dispatch + 판정."""
        orchestrator = DebateOrchestrator(optimized=settings.debate_orchestrator_optimized, client=client)
        executor = TurnExecutor(client, self.db)
        model_cache: dict[str, LLMModel] = {}
        usage_batch: list[TokenUsageLog] = []

        match_format = getattr(match, "format", "1v1")
        runner = get_format_runner(match_format)

        try:
            if match_format == "1v1":
                loop_result: TurnLoopResult = await runner(
                    executor, orchestrator, self.db, match, topic,
                    agent_a, agent_b, version_a, version_b, key_a, key_b,
                    model_cache, usage_batch,
                    parallel=orchestrator.optimized,
                )
            else:
                loop_result = await runner(
                    executor, orchestrator, self.db, match, topic,
                    agent_a, agent_b, model_cache, usage_batch,
                )
        except ForfeitError as forfeit:
            await ForfeitHandler(self.db).handle_retry_exhaustion(match, agent_a, agent_b, forfeit.forfeited_speaker)
            return

        match.penalty_a = loop_result.total_penalty_a
        match.penalty_b = loop_result.total_penalty_b
        await self.db.commit()

        turns_res = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match.id)
            .order_by(DebateTurnLog.turn_number, DebateTurnLog.speaker)
        )
        turns = list(turns_res.scalars().all())
        judgment = await orchestrator.judge(
            match, turns, topic, agent_a_name=agent_a.name, agent_b_name=agent_b.name
        )

        finalizer = MatchFinalizer(self.db)
        await finalizer.finalize(
            match, judgment, agent_a, agent_b,
            loop_result.model_cache, loop_result.usage_batch,
        )


# ── 매치 실행 진입점 ──────────────────────────────────────────────────────────

async def run_debate(match_id: str) -> None:
    """매치 실행. app-level DB 세션 풀로 백그라운드 실행."""
    async with async_session() as notify_db:
        try:
            from app.services.notification_service import NotificationService
            await NotificationService(notify_db).notify_match_event(match_id, "match_started")
            await notify_db.commit()
        except Exception:
            logger.warning("Start notification failed for match %s", match_id, exc_info=True)

    async with async_session() as db:
        try:
            engine = DebateEngine(db)
            await engine.run(match_id)
        except asyncio.CancelledError:
            logger.warning("Debate task cancelled for match %s — marking as error", match_id)
            try:
                await asyncio.shield(db.rollback())
                await asyncio.shield(db.execute(
                    update(DebateMatch)
                    .where(DebateMatch.id == match_id)
                    .values(status="error", finished_at=datetime.now(UTC))
                ))
                await asyncio.shield(db.commit())
                await asyncio.shield(publish_event(match_id, "error", {"message": "Match cancelled by server"}))
            except Exception:
                pass
            raise
        except Exception as exc:
            logger.error("Debate engine error for match %s: %s", match_id, exc, exc_info=True)
            try:
                await db.rollback()
                await db.execute(
                    update(DebateMatch)
                    .where(DebateMatch.id == match_id)
                    .values(status="error", finished_at=datetime.now(UTC))
                )
                await db.commit()
            except Exception:
                logger.error("Failed to mark match %s as error in DB", match_id)
            await publish_event(match_id, "error", {"message": str(exc)})
        else:
            async with async_session() as notify_db:
                try:
                    from app.services.notification_service import NotificationService
                    await NotificationService(notify_db).notify_match_event(match_id, "match_finished")
                    await notify_db.commit()
                except Exception:
                    logger.warning("Finish notification failed for match %s", match_id, exc_info=True)
