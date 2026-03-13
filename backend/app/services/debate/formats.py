"""토론 포맷별 턴 루프 함수 + 포맷 dispatch."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.services.debate.broadcast import publish_event
from app.services.debate.forfeit import ForfeitError
from app.services.debate.helpers import _resolve_api_key
from app.services.debate.orchestrator import DebateOrchestrator
from app.services.debate.turn_executor import TurnExecutor

logger = logging.getLogger(__name__)


@dataclass
class TurnLoopResult:
    claims_a: list[str]
    claims_b: list[str]
    total_penalty_a: int
    total_penalty_b: int
    model_cache: dict = field(default_factory=dict)
    usage_batch: list = field(default_factory=list)


# ── 이벤트 발행 헬퍼 ──────────────────────────────────────────────────────────

async def _publish_turn_event(match_id: str, turn: DebateTurnLog, review_result=None) -> None:
    """턴 완료 SSE 이벤트 발행."""
    await publish_event(match_id, "turn", {
        "turn_number": turn.turn_number,
        "speaker": turn.speaker,
        "action": turn.action,
        "claim": turn.claim,
        "evidence": turn.evidence,
        "penalties": turn.penalties,
        "penalty_total": turn.penalty_total,
        "response_time_ms": turn.response_time_ms,
        "input_tokens": turn.input_tokens,
        "output_tokens": turn.output_tokens,
        "is_blocked": turn.is_blocked,
        "review_result": review_result,
    })


async def _publish_review_event(match_id: str, turn_number: int, speaker: str, review: dict) -> None:
    """리뷰 결과 SSE 이벤트 발행."""
    await publish_event(match_id, "turn_review", {
        "turn_number": turn_number,
        "speaker": speaker,
        "logic_score": review["logic_score"],
        "violations": review["violations"],
        "feedback": review["feedback"],
        "blocked": review["block"],
    })


# ── 리뷰 결과 반영 헬퍼 ───────────────────────────────────────────────────────

def _apply_review_to_turn(
    turn: DebateTurnLog,
    review: dict,
    claims: list[str],
    penalty_total: int,
    update_last_claim: bool = False,
) -> int:
    """리뷰 결과를 TurnLog에 반영하고 누적 벌점을 반환.

    update_last_claim=True: 이미 append된 claims[-1]을 차단본으로 패치 (최적화 모드용)
    update_last_claim=False: claims에 직접 append (순차 모드용, 차단 시 blocked_claim append)
    """
    for vtype, vpenalty in review["penalties"].items():
        llm_key = f"llm_{vtype}"
        if turn.penalties is None:
            turn.penalties = {}
        turn.penalties[llm_key] = vpenalty
        turn.penalty_total += vpenalty
        penalty_total += vpenalty

    # block=True: 원문 대신 blocked_claim 텍스트로 교체
    if review["block"]:
        blocked = review["blocked_claim"]
        # parallel 모드: 이미 claims에 원본이 append됐으므로 마지막 항목을 패치
        if update_last_claim and claims:
            claims[-1] = blocked
        turn.is_blocked = True
        turn.claim = blocked
    elif not update_last_claim:
        # sequential 모드: 차단되지 않은 경우에만 claims에 추가
        claims.append(turn.claim)

    turn.review_result = {
        "logic_score": review["logic_score"],
        "violations": review["violations"],
        "feedback": review["feedback"],
        "blocked": review["block"],
        "skipped": review.get("skipped", False),
    }
    return penalty_total


# ── 오케스트레이터 토큰 기록 헬퍼 ────────────────────────────────────────────

async def _log_orchestrator_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    model_str: str,
    input_tokens: int,
    output_tokens: int,
    model_cache: dict | None = None,
    usage_batch: list | None = None,
) -> None:
    """오케스트레이터 LLM 호출 토큰을 token_usage_logs에 기록."""
    if input_tokens == 0 and output_tokens == 0:
        return

    # 캐시 우선 조회 — 매 호출마다 DB SELECT 방지
    if model_cache is not None and model_str in model_cache:
        model = model_cache[model_str]
    else:
        result = await db.execute(
            select(LLMModel).where(LLMModel.model_id == model_str)
        )
        model = result.scalar_one_or_none()
        if model_cache is not None and model is not None:
            model_cache[model_str] = model

    if model is None:
        logger.warning("_log_orchestrator_usage: model_id=%s not found in llm_models", model_str)
        return
    from app.services.debate.match_service import calculate_token_cost
    input_cost = calculate_token_cost(input_tokens, model.input_cost_per_1m)
    output_cost = calculate_token_cost(output_tokens, model.output_cost_per_1m)
    log = TokenUsageLog(
        user_id=user_id,
        session_id=None,
        llm_model_id=model.id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=input_cost + output_cost,
    )
    if usage_batch is not None:
        # 배치 모드: 매치 종료 시 일괄 INSERT
        usage_batch.append(log)
    else:
        db.add(log)


# ── 1v1 턴 루프 ───────────────────────────────────────────────────────────────

async def run_turns_1v1(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    key_a: str,
    key_b: str,
    model_cache: dict,
    usage_batch: list,
    parallel: bool,
) -> TurnLoopResult:
    """1v1 턴 루프. parallel=True면 롤링 create_task 병렬 패턴 사용.

    에이전트 발언이 재시도를 모두 소진하면 ForfeitError를 raise한다.
    """
    claims_a: list[str] = []
    claims_b: list[str] = []

    if parallel:
        total_penalty_a, total_penalty_b = await _run_parallel_turns(
            executor, orchestrator, db, match, topic,
            agent_a, agent_b, version_a, version_b, key_a, key_b,
            claims_a, claims_b, model_cache, usage_batch,
        )
    else:
        total_penalty_a, total_penalty_b = await _run_sequential_turns(
            executor, orchestrator, db, match, topic,
            agent_a, agent_b, version_a, version_b, key_a, key_b,
            claims_a, claims_b, model_cache, usage_batch,
        )

    return TurnLoopResult(claims_a, claims_b, total_penalty_a, total_penalty_b, model_cache, usage_batch)


async def _run_parallel_turns(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    key_a: str,
    key_b: str,
    claims_a: list[str],
    claims_b: list[str],
    model_cache: dict,
    usage_batch: list,
) -> tuple[int, int]:
    """롤링 병렬 패턴 턴 루프."""
    total_penalty_a = 0
    total_penalty_b = 0

    prev_b_review_task: asyncio.Task | None = None
    prev_turn_b: DebateTurnLog | None = None
    prev_b_turn_num: int = 0

    for turn_num in range(1, topic.max_turns + 1):
        # ★ 롤링 병렬: 이전 턴의 B 리뷰 결과를 A 실행 시작 전에 수집
        if settings.debate_turn_review_enabled and prev_b_review_task is not None:
            try:
                review_prev_b = await prev_b_review_task
            except Exception as exc:
                logger.error("B review task failed: %s — using fallback", exc)
                review_prev_b = orchestrator._review_fallback()
            prev_b_review_task = None

            if prev_turn_b is None:
                logger.error("prev_turn_b unexpectedly None at turn %d, skipping B review", turn_num)
            else:
                total_penalty_b = _apply_review_to_turn(
                    prev_turn_b, review_prev_b, claims_b,
                    total_penalty_b, update_last_claim=True
                )
                await _log_orchestrator_usage(
                    db, agent_b.owner_id, review_prev_b.get("model_id", ""),
                    review_prev_b["input_tokens"], review_prev_b["output_tokens"],
                    model_cache=model_cache, usage_batch=usage_batch,
                )
                await _publish_review_event(str(match.id), prev_b_turn_num, "agent_b", review_prev_b)

        # Agent A 턴
        turn_a = await executor.execute_with_retry(
            match, topic, turn_num, "agent_a",
            agent_a, version_a, key_a, claims_a, claims_b,
            my_accumulated_penalty=total_penalty_a,
        )
        if turn_a is None:
            raise ForfeitError(forfeited_speaker="agent_a")
        total_penalty_a += turn_a.penalty_total

        # B가 참조할 수 있도록 A 발언을 먼저 큐에 등록 (검토 전 원본)
        claims_a.append(turn_a.claim)

        # ★ gather 전에 A turn 이벤트 먼저 발행 — B 스트리밍이 pendingStreamingTurn
        # 없이 바로 streamingTurn으로 표시되도록 순서 보장.
        await _publish_turn_event(str(match.id), turn_a, review_result=None)

        if settings.debate_turn_review_enabled:
            # A 검토를 백그라운드 태스크로 시작 — B 실행과 병렬로 진행
            review_a_task = asyncio.create_task(
                orchestrator.review_turn(
                    topic=topic.title,
                    speaker="agent_a",
                    turn_number=turn_num,
                    claim=turn_a.claim,
                    evidence=turn_a.evidence,
                    action=turn_a.action,
                    opponent_last_claim=claims_b[-1] if claims_b else None,
                    recent_history=claims_a[-2:] if claims_a else None,
                )
            )

            # B 실행 (A 검토와 병렬)
            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                agent_b, version_b, key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
            )
            if turn_b is None:
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total

            # B 발언을 검토 전에 즉시 등록 — 다음 턴 A가 원본 클레임을 참조할 수 있도록
            claims_b.append(turn_b.claim)

            # ★ B 턴 이벤트 즉시 발행 — A 검토 완료를 기다리지 않으므로 스트리밍 지연 없음
            await _publish_turn_event(str(match.id), turn_b, review_result=None)

            # ★ B 리뷰를 백그라운드 태스크로 시작 — 다음 턴 A 실행과 병렬로 진행
            prev_b_review_task = asyncio.create_task(
                orchestrator.review_turn(
                    topic=topic.title,
                    speaker="agent_b",
                    turn_number=turn_num,
                    claim=turn_b.claim,
                    evidence=turn_b.evidence,
                    action=turn_b.action,
                    opponent_last_claim=claims_a[-1] if claims_a else None,
                    recent_history=claims_b[-2:] if claims_b else None,
                )
            )
            prev_turn_b = turn_b
            prev_b_turn_num = turn_num

            # A 검토 완료 대기 (B 실행 동안 이미 상당 부분 진행됨)
            review_start = time.monotonic()
            try:
                review_a = await review_a_task
            except Exception as exc:
                logger.error("A review task failed: %s — using fallback", exc)
                review_a = orchestrator._review_fallback()
            review_elapsed = time.monotonic() - review_start

            # A 검토 결과 반영 (차단 시 claims_a 마지막 항목 패치)
            total_penalty_a = _apply_review_to_turn(
                turn_a, review_a, claims_a,
                total_penalty_a, update_last_claim=True
            )
            await _log_orchestrator_usage(
                db, agent_a.owner_id, review_a.get("model_id", ""),
                review_a["input_tokens"], review_a["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
            await _publish_review_event(str(match.id), turn_num, "agent_a", review_a)
        else:
            # 리뷰 비활성: B 순차 실행
            b_exec_start = time.monotonic()
            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                agent_b, version_b, key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
            )
            review_elapsed = time.monotonic() - b_exec_start
            if turn_b is None:
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total
            claims_b.append(turn_b.claim)
            await _publish_turn_event(str(match.id), turn_b)

        # 라운드 사이 딜레이 (마지막 제외)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    # ★ 롤링 병렬: 루프 종료 후 마지막 B 리뷰 수집
    if settings.debate_turn_review_enabled and prev_b_review_task is not None:
        try:
            review_last_b = await prev_b_review_task
        except Exception as exc:
            logger.error("Last B review task failed: %s — using fallback", exc)
            review_last_b = orchestrator._review_fallback()

        if prev_turn_b is None:
            logger.error("prev_turn_b unexpectedly None after loop, skipping last B review")
        else:
            total_penalty_b = _apply_review_to_turn(
                prev_turn_b, review_last_b, claims_b,
                total_penalty_b, update_last_claim=True
            )
            await _log_orchestrator_usage(
                db, agent_b.owner_id, review_last_b.get("model_id", ""),
                review_last_b["input_tokens"], review_last_b["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
            await _publish_review_event(str(match.id), prev_b_turn_num, "agent_b", review_last_b)

    return total_penalty_a, total_penalty_b


async def _run_sequential_turns(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    key_a: str,
    key_b: str,
    claims_a: list[str],
    claims_b: list[str],
    model_cache: dict,
    usage_batch: list,
) -> tuple[int, int]:
    """순차 턴 루프."""
    total_penalty_a = 0
    total_penalty_b = 0

    for turn_num in range(1, topic.max_turns + 1):
        # Agent A 턴
        turn_a = await executor.execute_with_retry(
            match, topic, turn_num, "agent_a",
            agent_a, version_a, key_a, claims_a, claims_b,
            my_accumulated_penalty=total_penalty_a,
        )
        if turn_a is None:
            raise ForfeitError(forfeited_speaker="agent_a")
        total_penalty_a += turn_a.penalty_total

        if settings.debate_turn_review_enabled:
            review_start = time.monotonic()
            review_a = await orchestrator.review_turn(
                topic=topic.title,
                speaker="agent_a",
                turn_number=turn_num,
                claim=turn_a.claim,
                evidence=turn_a.evidence,
                action=turn_a.action,
                opponent_last_claim=claims_b[-1] if claims_b else None,
                recent_history=claims_a[-2:] if claims_a else None,
            )
            review_elapsed = time.monotonic() - review_start

            total_penalty_a = _apply_review_to_turn(
                turn_a, review_a, claims_a, total_penalty_a, update_last_claim=False
            )
            await _log_orchestrator_usage(
                db, agent_a.owner_id, review_a.get("model_id", ""),
                review_a["input_tokens"], review_a["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
        else:
            review_a = None
            review_elapsed = 0.0
            claims_a.append(turn_a.claim)

        await _publish_turn_event(str(match.id), turn_a, turn_a.review_result)
        if review_a is not None:
            await _publish_review_event(str(match.id), turn_num, "agent_a", review_a)

        # 관전 UX: 딜레이에서 검토 소요시간 차감
        remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)

        # Agent B 턴
        turn_b = await executor.execute_with_retry(
            match, topic, turn_num, "agent_b",
            agent_b, version_b, key_b, claims_b, claims_a,
            my_accumulated_penalty=total_penalty_b,
        )
        if turn_b is None:
            raise ForfeitError(forfeited_speaker="agent_b")
        total_penalty_b += turn_b.penalty_total

        if settings.debate_turn_review_enabled:
            review_start = time.monotonic()
            review_b = await orchestrator.review_turn(
                topic=topic.title,
                speaker="agent_b",
                turn_number=turn_num,
                claim=turn_b.claim,
                evidence=turn_b.evidence,
                action=turn_b.action,
                opponent_last_claim=claims_a[-1] if claims_a else None,
                recent_history=claims_b[-2:] if claims_b else None,
            )
            review_elapsed = time.monotonic() - review_start

            total_penalty_b = _apply_review_to_turn(
                turn_b, review_b, claims_b, total_penalty_b, update_last_claim=False
            )
            await _log_orchestrator_usage(
                db, agent_b.owner_id, review_b.get("model_id", ""),
                review_b["input_tokens"], review_b["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
        else:
            review_b = None
            review_elapsed = 0.0
            claims_b.append(turn_b.claim)

        await _publish_turn_event(str(match.id), turn_b, turn_b.review_result)
        if review_b is not None:
            await _publish_review_event(str(match.id), turn_num, "agent_b", review_b)

        # 라운드 사이 딜레이 (마지막 제외)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    return total_penalty_a, total_penalty_b


# ── 멀티에이전트 턴 루프 ──────────────────────────────────────────────────────

async def run_turns_multi(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    model_cache: dict,
    usage_batch: list,
) -> TurnLoopResult:
    """멀티에이전트 턴 루프 (라운드 로빈)."""
    from app.models.debate_match import DebateMatchParticipant

    parts_res = await db.execute(
        select(DebateMatchParticipant)
        .where(DebateMatchParticipant.match_id == match.id)
        .order_by(DebateMatchParticipant.team, DebateMatchParticipant.slot)
    )
    parts = list(parts_res.scalars().all())
    team_a = [p for p in parts if p.team == "A"]
    team_b = [p for p in parts if p.team == "B"]

    if not team_a or not team_b:
        logger.warning("Multi-agent match %s has no participants, skipping", match.id)
        return TurnLoopResult([], [], 0, 0, model_cache, usage_batch)

    max_slots = max(len(team_a), len(team_b))

    # 루프 진입 전 에이전트/버전을 한 번에 배치 조회
    from app.models.debate_agent import DebateAgentVersion as AgentVersion
    all_agent_ids = list({p.agent_id for p in parts if p.agent_id is not None})
    agents_res = await db.execute(
        select(DebateAgent).where(DebateAgent.id.in_(all_agent_ids))
    )
    agents_cache: dict = {str(a.id): a for a in agents_res.scalars().all()}

    all_version_ids = list({p.version_id for p in parts if p.version_id is not None})
    versions_cache: dict = {}
    if all_version_ids:
        versions_res = await db.execute(
            select(AgentVersion).where(AgentVersion.id.in_(all_version_ids))
        )
        versions_cache = {str(v.id): v for v in versions_res.scalars().all()}

    claims_a: list[str] = []
    claims_b: list[str] = []
    total_penalty_a = 0
    total_penalty_b = 0

    for turn_num in range(1, topic.max_turns + 1):
        for i in range(max_slots):
            a_part = team_a[i % len(team_a)]
            b_part = team_b[i % len(team_b)]

            multi_agent_a = agents_cache.get(str(a_part.agent_id))
            multi_agent_b = agents_cache.get(str(b_part.agent_id))

            if multi_agent_a is None or multi_agent_b is None:
                logger.warning("Multi-agent: agent not found, slot %d turn %d", i, turn_num)
                continue

            key_a = _resolve_api_key(multi_agent_a)
            key_b = _resolve_api_key(multi_agent_b)

            ver_a = versions_cache.get(str(a_part.version_id)) if a_part.version_id else None
            ver_b = versions_cache.get(str(b_part.version_id)) if b_part.version_id else None

            turn_a = await executor.execute_with_retry(
                match, topic, turn_num, "agent_a",
                multi_agent_a, ver_a, key_a, claims_a, claims_b,
                my_accumulated_penalty=total_penalty_a,
            )
            if turn_a is None:
                raise ForfeitError(forfeited_speaker="agent_a")
            total_penalty_a += turn_a.penalty_total

            if settings.debate_turn_review_enabled:
                review = await orchestrator.review_turn(
                    topic=topic.title,
                    speaker=f"agent_a_slot{i}",
                    turn_number=turn_num,
                    claim=turn_a.claim,
                    evidence=turn_a.evidence,
                    action=turn_a.action,
                    opponent_last_claim=claims_b[-1] if claims_b else None,
                    recent_history=claims_a[-2:] if claims_a else None,
                )
                total_penalty_a = _apply_review_to_turn(
                    turn_a, review, claims_a, total_penalty_a, update_last_claim=False
                )
                await _log_orchestrator_usage(
                    db, multi_agent_a.owner_id, review.get("model_id", ""),
                    review["input_tokens"], review["output_tokens"],
                    model_cache=model_cache, usage_batch=usage_batch,
                )
                await _publish_review_event(str(match.id), turn_num, f"agent_a_slot{i}", review)
            else:
                claims_a.append(turn_a.claim)

            # speaker 이름을 슬롯 기반으로 오버라이드해 1v1과 동일한 필드셋 발행
            await publish_event(str(match.id), "turn", {
                "turn_number": turn_num,
                "speaker": f"agent_a_slot{i}",
                "action": turn_a.action,
                "claim": turn_a.claim,
                "evidence": turn_a.evidence,
                "penalties": turn_a.penalties,
                "penalty_total": turn_a.penalty_total,
                "response_time_ms": turn_a.response_time_ms,
                "input_tokens": turn_a.input_tokens,
                "output_tokens": turn_a.output_tokens,
                "is_blocked": turn_a.is_blocked,
                "review_result": None,
            })

            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                multi_agent_b, ver_b, key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
            )
            if turn_b is None:
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total

            if settings.debate_turn_review_enabled:
                review = await orchestrator.review_turn(
                    topic=topic.title,
                    speaker=f"agent_b_slot{i}",
                    turn_number=turn_num,
                    claim=turn_b.claim,
                    evidence=turn_b.evidence,
                    action=turn_b.action,
                    opponent_last_claim=claims_a[-1] if claims_a else None,
                    recent_history=claims_b[-2:] if claims_b else None,
                )
                total_penalty_b = _apply_review_to_turn(
                    turn_b, review, claims_b, total_penalty_b, update_last_claim=False
                )
                await _log_orchestrator_usage(
                    db, multi_agent_b.owner_id, review.get("model_id", ""),
                    review["input_tokens"], review["output_tokens"],
                    model_cache=model_cache, usage_batch=usage_batch,
                )
                await _publish_review_event(str(match.id), turn_num, f"agent_b_slot{i}", review)
            else:
                claims_b.append(turn_b.claim)

            await publish_event(str(match.id), "turn", {
                "turn_number": turn_num,
                "speaker": f"agent_b_slot{i}",
                "action": turn_b.action,
                "claim": turn_b.claim,
                "evidence": turn_b.evidence,
                "penalties": turn_b.penalties,
                "penalty_total": turn_b.penalty_total,
                "response_time_ms": turn_b.response_time_ms,
                "input_tokens": turn_b.input_tokens,
                "output_tokens": turn_b.output_tokens,
                "is_blocked": turn_b.is_blocked,
                "review_result": None,
            })

    return TurnLoopResult(claims_a, claims_b, total_penalty_a, total_penalty_b, model_cache, usage_batch)


# ── 포맷 dispatch ──────────────────────────────────────────────────────────────

# 새 형식 추가 = 함수 1개 + 이 dict 1줄
_FORMAT_RUNNERS: dict[str, Callable] = {
    "1v1": run_turns_1v1,
    "2v2": run_turns_multi,
    "3v3": run_turns_multi,
}


def get_format_runner(match_format: str) -> Callable:
    return _FORMAT_RUNNERS.get(match_format, run_turns_1v1)
