"""토론 포맷별 턴 루프 함수 + 포맷 dispatch."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
from app.services.debate.evidence_search import EvidenceResult, EvidenceSearchService
from app.services.debate.forfeit import ForfeitError
from app.services.debate.helpers import _resolve_api_key
from app.services.debate.orchestrator import DebateOrchestrator
from app.services.debate.turn_executor import TurnExecutor

_evidence_service = EvidenceSearchService()
_TOOL_USE_PROVIDERS = frozenset({"openai", "anthropic", "google"})

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.debate.control_plane import OrchestrationControlPlane


@dataclass
class TurnLoopResult:
    """턴 루프 종료 후 DebateEngine에 반환하는 집계 결과.

    Attributes:
        claims_a: A측 발언 목록 (차단된 경우 blocked_claim 텍스트로 대체됨).
        claims_b: B측 발언 목록 (차단된 경우 blocked_claim 텍스트로 대체됨).
        total_penalty_a: A측 누적 벌점 합계.
        total_penalty_b: B측 누적 벌점 합계.
        model_cache: LLMModel 캐시 (model_id → LLMModel). finalizer에 전달.
        usage_batch: 커밋 전 모아둔 TokenUsageLog 목록. finalizer에서 일괄 INSERT.
    """

    claims_a: list[str]
    claims_b: list[str]
    total_penalty_a: int
    total_penalty_b: int
    model_cache: dict = field(default_factory=dict)
    usage_batch: list = field(default_factory=list)


# ── 이벤트 발행 헬퍼 ──────────────────────────────────────────────────────────

async def _publish_turn_event(
    match_id: str,
    turn: DebateTurnLog,
    review_result=None,
    event_meta: dict | None = None,
) -> None:
    """턴 완료 SSE 이벤트를 발행한다.

    Args:
        match_id: 이벤트를 발행할 매치 UUID 문자열.
        turn: 완료된 턴 로그 (DB 플러시 완료 상태).
        review_result: LLM 검토 결과 dict. None이면 review_result 필드를 null로 발행.
    """
    payload = {
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
    }
    if event_meta:
        payload.update(event_meta)
    await publish_event(match_id, "turn", payload)


async def _publish_review_event(
    match_id: str,
    turn_number: int,
    speaker: str,
    review: dict,
    event_meta: dict | None = None,
    fallback_reason: str | None = None,
) -> None:
    """리뷰 결과 SSE 이벤트를 발행한다.

    Args:
        match_id: 이벤트를 발행할 매치 UUID 문자열.
        turn_number: 리뷰 대상 턴 번호.
        speaker: 발언자 ('agent_a' | 'agent_b' | 슬롯 레이블).
        review: DebateOrchestrator.review_turn()이 반환한 결과 dict.
    """
    payload = {
        "turn_number": turn_number,
        "speaker": speaker,
        "logic_score": review["logic_score"],
        "violations": review["violations"],
        "feedback": review["feedback"],
        "blocked": review["block"],
    }
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    if event_meta:
        payload.update(event_meta)
    await publish_event(match_id, "turn_review", payload)


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
        elif not update_last_claim:
            # sequential 모드: 차단 발언도 인덱스 보존을 위해 blocked_claim 텍스트로 추가
            # (누락 시 다음 턴의 opponent_last_claim 인덱스가 어긋남)
            claims.append(blocked)
        turn.is_blocked = True
        turn.claim = blocked
    elif not update_last_claim:
        # sequential 모드: 차단되지 않은 경우에만 원본 발언을 claims에 추가
        claims.append(turn.claim)

    turn.review_result = {
        "logic_score": review["logic_score"],
        "violations": review["violations"],
        "feedback": review["feedback"],
        "blocked": review["block"],
        "skipped": review.get("skipped", False),
    }
    return penalty_total


def _has_severe_violation(review: dict) -> bool:
    """review dict에 severity=severe인 위반이 하나 이상 있으면 True."""
    return any(v.get("severity") == "severe" for v in review.get("violations", []))


def _update_accumulated_violations(accumulated: dict[str, int], review: dict) -> None:
    """review의 violations를 accumulated 딕셔너리에 카운트 누적한다."""
    for v in review.get("violations", []):
        vtype = v.get("type", "")
        if vtype:
            accumulated[vtype] = accumulated.get(vtype, 0) + 1


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
    """오케스트레이터 LLM 호출 토큰을 token_usage_logs에 기록한다.

    input_tokens == output_tokens == 0이면 즉시 반환 (폴백/스킵된 호출).
    model_cache를 활용해 동일 모델 반복 DB 조회를 방지한다.
    usage_batch가 None이면 즉시 db.add(), 있으면 배치에 추가 (매치 종료 시 일괄 INSERT).

    Args:
        db: 비동기 DB 세션.
        user_id: 사용량을 기록할 사용자 UUID.
        model_str: LLM 모델 ID 문자열 (llm_models.model_id).
        input_tokens: 입력 토큰 수.
        output_tokens: 출력 토큰 수.
        model_cache: model_id → LLMModel 캐시 dict. None이면 매번 DB 조회.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록. None이면 즉시 INSERT.
    """
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
    api_key_a: str,
    api_key_b: str,
    model_cache: dict,
    usage_batch: list,
    parallel: bool,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> TurnLoopResult:
    """1v1 포맷 턴 루프 진입점.

    parallel=True이면 롤링 create_task 병렬 패턴(_run_parallel_turns)을 사용하고,
    parallel=False이면 순차 패턴(_run_sequential_turns)을 사용한다.
    에이전트 발언이 재시도를 모두 소진하면 ForfeitError를 raise한다.

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 매치.
        topic: 토론 주제.
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        version_a: A측 에이전트 버전 스냅샷.
        version_b: B측 에이전트 버전 스냅샷.
        api_key_a: A측 LLM API 키.
        api_key_b: B측 LLM API 키.
        model_cache: LLMModel 캐시 dict (호출 간 공유).
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.
        parallel: True면 병렬 패턴, False면 순차 패턴 사용.

    Returns:
        TurnLoopResult: 발언 목록·누적 벌점·캐시 등 턴 루프 집계 결과.

    Raises:
        ForfeitError: 에이전트 발언이 모든 재시도 후에도 실패한 경우.
    """
    claims_a: list[str] = []
    claims_b: list[str] = []

    if parallel:
        total_penalty_a, total_penalty_b = await _run_parallel_turns(
            executor, orchestrator, db, match, topic,
            agent_a, agent_b, version_a, version_b, api_key_a, api_key_b,
            claims_a, claims_b, model_cache, usage_batch, control_plane=control_plane,
        )
    else:
        total_penalty_a, total_penalty_b = await _run_sequential_turns(
            executor, orchestrator, db, match, topic,
            agent_a, agent_b, version_a, version_b, api_key_a, api_key_b,
            claims_a, claims_b, model_cache, usage_batch, control_plane=control_plane,
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
    api_key_a: str,
    api_key_b: str,
    claims_a: list[str],
    claims_b: list[str],
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> tuple[int, int]:
    """롤링 병렬 패턴 턴 루프.

    매 턴마다 A 검토와 B 실행을 asyncio.create_task로 병렬화한다.
    이전 턴의 B 리뷰 결과는 다음 턴 A 실행 직전에 수집하는 '롤링' 방식으로
    검토 대기시간을 B 실행 시간에 숨긴다 (전체 지연 약 37% 단축).

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 매치.
        topic: 토론 주제.
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        version_a: A측 에이전트 버전 스냅샷.
        version_b: B측 에이전트 버전 스냅샷.
        api_key_a: A측 LLM API 키.
        api_key_b: B측 LLM API 키.
        claims_a: A측 발언 누적 목록 (in-out 참조).
        claims_b: B측 발언 누적 목록 (in-out 참조).
        model_cache: LLMModel 캐시 dict.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.

    Returns:
        (total_penalty_a, total_penalty_b) 누적 벌점 튜플.

    Raises:
        ForfeitError: A 또는 B 발언이 모든 재시도 후에도 실패한 경우.
    """
    total_penalty_a = 0
    total_penalty_b = 0

    # settings가 MagicMock인 테스트 환경에서는 evidence task를 생성하지 않도록 엄밀 타입 검사
    # bool 타입인 경우만 True로 간주 — MagicMock은 bool이 아니므로 False로 처리됨
    _ev_enabled = isinstance(
        getattr(settings, "debate_evidence_search_enabled", False), bool
    ) and settings.debate_evidence_search_enabled

    # 매치 단위 사용 출처 추적 — 동일 URL이 여러 턴에서 반복 인용되지 않도록
    used_sources: set[str] = set()

    prev_b_review_task: asyncio.Task | None = None
    prev_b_evidence_task: asyncio.Task | None = None
    prev_turn_b: DebateTurnLog | None = None
    prev_b_turn_num: int = 0
    # 이전 턴 evidence를 다음 턴 시스템 프롬프트에 주입 — 연속 논거 구성 지원
    prev_evidence_a: str | None = None
    prev_evidence_b: str | None = None
    consecutive_severe_a = 0
    consecutive_severe_b = 0
    accumulated_violations_a: dict[str, int] = {}
    accumulated_violations_b: dict[str, int] = {}

    for turn_num in range(1, topic.max_turns + 1):
        # ★ 롤링 병렬: 이전 턴의 B 리뷰 + 근거 검색 결과를 A 실행 시작 전에 수집
        if settings.debate_turn_review_enabled and prev_b_review_task is not None:
            try:
                review_prev_b = await prev_b_review_task
            except Exception as exc:
                logger.error("B review task failed: %s — using fallback", exc)
                review_prev_b = orchestrator.review_fallback()
            prev_b_review_task = None

            # B evidence 수집 (review와 함께 이미 대부분 완료됨)
            if prev_b_evidence_task is not None and prev_turn_b is not None:
                try:
                    evidence_b = await prev_b_evidence_task
                    raw = prev_turn_b.raw_response or {}
                    if isinstance(evidence_b, EvidenceResult) and raw.get("tool_used") != "web_search":
                        prev_turn_b.evidence = evidence_b.format()
                        used_sources.update(evidence_b.sources)
                        await db.flush()
                        await publish_event(str(match.id), "turn_evidence_patch", {
                            "turn_number": prev_b_turn_num,
                            "speaker": "agent_b",
                            "evidence": prev_turn_b.evidence,
                        })
                except Exception as exc:
                    logger.warning("B evidence task failed: %s", exc)
                prev_b_evidence_task = None
            # 이번 수집된 B evidence를 다음 턴 시스템 프롬프트에 주입하기 위해 저장
            if prev_turn_b is not None:
                prev_evidence_b = prev_turn_b.evidence

            if prev_turn_b is None:
                logger.error("prev_turn_b unexpectedly None at turn %d, skipping B review", turn_num)
                # 비정상 경로: B 발언 없이 리뷰 태스크가 생성된 경우 카운터 리셋 — 이전 severe가 누적되지 않도록
                consecutive_severe_b = 0
            else:
                total_penalty_b = _apply_review_to_turn(
                    prev_turn_b, review_prev_b, claims_b,
                    total_penalty_b, update_last_claim=True
                )
                if _has_severe_violation(review_prev_b):
                    consecutive_severe_b += 1
                else:
                    consecutive_severe_b = 0
                _update_accumulated_violations(accumulated_violations_b, review_prev_b)
                _streak = settings.debate_forfeit_on_severe_streak
                if _streak and consecutive_severe_b >= _streak:
                    if prev_b_evidence_task and not prev_b_evidence_task.done():
                        prev_b_evidence_task.cancel()
                    raise ForfeitError(forfeited_speaker="agent_b")
                await _log_orchestrator_usage(
                    db, agent_b.owner_id, review_prev_b.get("model_id", ""),
                    review_prev_b["input_tokens"], review_prev_b["output_tokens"],
                    model_cache=model_cache, usage_batch=usage_batch,
                )
                fallback_reason = review_prev_b.get("fallback_reason")
                if control_plane and fallback_reason:
                    control_plane.mark_fallback(
                        fallback_reason,
                        stage="review",
                        turn_number=prev_b_turn_num,
                        speaker="agent_b",
                    )
                await _publish_review_event(
                    str(match.id),
                    prev_b_turn_num,
                    "agent_b",
                    review_prev_b,
                    event_meta=control_plane.event_meta(
                        turn_number=prev_b_turn_num,
                        speaker="agent_b",
                        fallback_reason=fallback_reason,
                    ) if control_plane else None,
                    fallback_reason=fallback_reason,
                )

        # Agent A 턴
        turn_a = await executor.execute_with_retry(
            match, topic, turn_num, "agent_a",
            agent_a, version_a, api_key_a, claims_a, claims_b,
            my_accumulated_penalty=total_penalty_a,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
            prev_evidence=prev_evidence_a,
        )
        if turn_a is None:
            for _t in [prev_b_review_task, prev_b_evidence_task]:
                if _t and not _t.done():
                    _t.cancel()
            raise ForfeitError(forfeited_speaker="agent_a")
        total_penalty_a += turn_a.penalty_total

        # B가 참조할 수 있도록 A 발언을 먼저 큐에 등록 (검토 전 원본)
        # P3: recent_history를 append 전에 캡처 — 현재 발언이 이전 발언 목록에 섞이지 않도록
        recent_history_a = claims_a[-2:] if claims_a else None
        claims_a.append(turn_a.claim)

        # ★ gather 전에 A turn 이벤트 먼저 발행 — B 스트리밍이 pendingStreamingTurn
        # 없이 바로 streamingTurn으로 표시되도록 순서 보장.
        await _publish_turn_event(
            str(match.id),
            turn_a,
            review_result=None,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
        )

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
                    recent_history=recent_history_a,
                    trace_id=control_plane.runtime.trace_id if control_plane else None,
                    orchestration_mode=control_plane.runtime.mode if control_plane else None,
                    tools_available=(
                        settings.debate_tool_use_enabled
                        and topic.tools_enabled
                        and agent_a.provider in _TOOL_USE_PROVIDERS
                    ),
                    tool_result=(turn_a.raw_response or {}).get("tool_raw_content") or (turn_a.raw_response or {}).get("tool_result"),
                    debater_position="A (찬성)",
                    opponent_recent_history=claims_b[-2:] if claims_b else None,
                    max_turns=topic.max_turns,
                    accumulated_violations=accumulated_violations_a,
                )
            )
            # A 근거 검색도 백그라운드 시작 — B 실행 시간에 숨김
            # tool_used=web_search인 경우 이미 검색 결과가 있으므로 사후 evidence 검색 스킵
            evidence_a_task: asyncio.Task | None = asyncio.create_task(
                _evidence_service.search(turn_a.claim, exclude_urls=set(used_sources))
            ) if (_ev_enabled and turn_a.claim and (turn_a.raw_response or {}).get("tool_used") != "web_search") else None

            # B 실행 (A 검토와 병렬)
            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                agent_b, version_b, api_key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
                prev_evidence=prev_evidence_b,
            )
            if turn_b is None:
                # P1: turn_b 실패 시 현재 실행 중인 review_a_task와 evidence_a_task도 취소
                for _t in [review_a_task, evidence_a_task, prev_b_review_task, prev_b_evidence_task]:
                    if _t and not _t.done():
                        _t.cancel()
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total

            # B 발언을 검토 전에 즉시 등록 — 다음 턴 A가 원본 클레임을 참조할 수 있도록
            # P3: recent_history를 append 전에 캡처
            recent_history_b = claims_b[-2:] if claims_b else None
            claims_b.append(turn_b.claim)

            # ★ B 턴 이벤트 즉시 발행 — A 검토 완료를 기다리지 않으므로 스트리밍 지연 없음
            await _publish_turn_event(
                str(match.id),
                turn_b,
                review_result=None,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            )

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
                    recent_history=recent_history_b,
                    trace_id=control_plane.runtime.trace_id if control_plane else None,
                    orchestration_mode=control_plane.runtime.mode if control_plane else None,
                    tools_available=(
                        settings.debate_tool_use_enabled
                        and topic.tools_enabled
                        and agent_b.provider in _TOOL_USE_PROVIDERS
                    ),
                    tool_result=(turn_b.raw_response or {}).get("tool_raw_content") or (turn_b.raw_response or {}).get("tool_result"),
                    debater_position="B (반대)",
                    opponent_recent_history=claims_a[-2:] if claims_a else None,
                    max_turns=topic.max_turns,
                    accumulated_violations=accumulated_violations_b,
                )
            )
            # B 근거 검색도 백그라운드 시작 — 다음 턴 A 실행 시간에 숨김
            # tool_used=web_search인 경우 이미 검색 결과가 있으므로 사후 evidence 검색 스킵
            prev_b_evidence_task = asyncio.create_task(
                _evidence_service.search(turn_b.claim, exclude_urls=set(used_sources))
            ) if (_ev_enabled and turn_b.claim and (turn_b.raw_response or {}).get("tool_used") != "web_search") else None
            prev_turn_b = turn_b
            prev_b_turn_num = turn_num

            # A 검토 + 근거 검색 완료 대기 (B 실행 동안 이미 상당 부분 진행됨)
            review_start = time.monotonic()
            try:
                review_a = await review_a_task
            except Exception as exc:
                logger.error("A review task failed: %s — using fallback", exc)
                review_a = orchestrator.review_fallback()
            if evidence_a_task is not None:
                try:
                    evidence_a = await evidence_a_task
                    raw = turn_a.raw_response or {}
                    if isinstance(evidence_a, EvidenceResult) and raw.get("tool_used") != "web_search":
                        turn_a.evidence = evidence_a.format()
                        used_sources.update(evidence_a.sources)
                        await db.flush()
                        await publish_event(str(match.id), "turn_evidence_patch", {
                            "turn_number": turn_num,
                            "speaker": "agent_a",
                            "evidence": turn_a.evidence,
                        })
                except Exception as exc:
                    logger.warning("A evidence task failed: %s", exc)
            # 이번 턴 A evidence를 다음 턴 시스템 프롬프트에 주입하기 위해 저장
            prev_evidence_a = turn_a.evidence
            evidence_a_task = None
            turn_elapsed = time.monotonic() - review_start

            # A 검토 결과 반영 (차단 시 claims_a 마지막 항목 패치)
            total_penalty_a = _apply_review_to_turn(
                turn_a, review_a, claims_a,
                total_penalty_a, update_last_claim=True
            )
            if _has_severe_violation(review_a):
                consecutive_severe_a += 1
            else:
                consecutive_severe_a = 0
            _update_accumulated_violations(accumulated_violations_a, review_a)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_a >= _streak:
                # 진행 중인 B 리뷰·근거 태스크 취소
                for _t in [prev_b_review_task, prev_b_evidence_task]:
                    if _t and not _t.done():
                        _t.cancel()
                raise ForfeitError(forfeited_speaker="agent_a")
            await _log_orchestrator_usage(
                db, agent_a.owner_id, review_a.get("model_id", ""),
                review_a["input_tokens"], review_a["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
            fallback_reason = review_a.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=turn_num,
                    speaker="agent_a",
                )
            await _publish_review_event(
                str(match.id),
                turn_num,
                "agent_a",
                review_a,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a", fallback_reason=fallback_reason)
                if control_plane else None,
                fallback_reason=fallback_reason,
            )
        else:
            # 리뷰 비활성: B 순차 실행
            b_exec_start = time.monotonic()
            turn_b = await executor.execute_with_retry(
                match, topic, turn_num, "agent_b",
                agent_b, version_b, api_key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            )
            turn_elapsed = time.monotonic() - b_exec_start
            if turn_b is None:
                raise ForfeitError(forfeited_speaker="agent_b")
            total_penalty_b += turn_b.penalty_total
            claims_b.append(turn_b.claim)
            await _publish_turn_event(
                str(match.id),
                turn_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            )

        # 라운드 사이 딜레이 (마지막 제외)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - turn_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    # ★ 롤링 병렬: 루프 종료 후 마지막 B 리뷰·근거 수집
    # review_task를 먼저 await — LLM 호출(수백 ms) 완료 후 evidence_task도 done()일 가능성이 높아짐
    if settings.debate_turn_review_enabled and prev_b_review_task is not None:
        try:
            review_last_b = await prev_b_review_task
        except Exception as exc:
            logger.error("Last B review task failed: %s — using fallback", exc)
            review_last_b = orchestrator.review_fallback()

        if prev_turn_b is None:
            logger.error("prev_turn_b unexpectedly None after loop, skipping last B review")
        else:
            total_penalty_b = _apply_review_to_turn(
                prev_turn_b, review_last_b, claims_b,
                total_penalty_b, update_last_claim=True
            )
            if _has_severe_violation(review_last_b):
                consecutive_severe_b += 1
            else:
                consecutive_severe_b = 0
            _update_accumulated_violations(accumulated_violations_b, review_last_b)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_b >= _streak:
                # 루프 후 마지막 B 검토에서 임계치 도달 — prev_b_evidence_task는 L722-739에서 처리되지 못하므로 직접 취소
                if prev_b_evidence_task and not prev_b_evidence_task.done():
                    prev_b_evidence_task.cancel()
                raise ForfeitError(forfeited_speaker="agent_b")
            await _log_orchestrator_usage(
                db, agent_b.owner_id, review_last_b.get("model_id", ""),
                review_last_b["input_tokens"], review_last_b["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
            fallback_reason = review_last_b.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=prev_b_turn_num,
                    speaker="agent_b",
                )
            await _publish_review_event(
                str(match.id),
                prev_b_turn_num,
                "agent_b",
                review_last_b,
                event_meta=control_plane.event_meta(
                    turn_number=prev_b_turn_num,
                    speaker="agent_b",
                    fallback_reason=fallback_reason,
                ) if control_plane else None,
                fallback_reason=fallback_reason,
            )

    # review_task await 후 evidence_task 체크 — review LLM 완료 시점에 evidence도 done()일 가능성 높음
    if settings.debate_turn_review_enabled and prev_b_evidence_task is not None and prev_turn_b is not None:
        if prev_b_evidence_task.done() and not prev_b_evidence_task.cancelled():
            try:
                evidence_last_b = prev_b_evidence_task.result()
                raw = prev_turn_b.raw_response or {}
                if isinstance(evidence_last_b, EvidenceResult) and raw.get("tool_used") != "web_search":
                    prev_turn_b.evidence = evidence_last_b.format()
                    await db.flush()
                    await publish_event(str(match.id), "turn_evidence_patch", {
                        "turn_number": prev_b_turn_num,
                        "speaker": "agent_b",
                        "evidence": prev_turn_b.evidence,
                    })
            except Exception as exc:
                logger.warning("Last B evidence task failed: %s", exc)
        else:
            # 미완료 태스크 취소 — 루프 종료 후 고아 태스크로 남지 않도록
            prev_b_evidence_task.cancel()

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
    api_key_a: str,
    api_key_b: str,
    claims_a: list[str],
    claims_b: list[str],
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
) -> tuple[int, int]:
    """순차 턴 루프. DEBATE_ORCHESTRATOR_OPTIMIZED=false 시 또는 롤백 경로에서 사용.

    A 실행 → A 검토 → B 실행 → B 검토 순서로 순차 처리.
    검토 소요시간은 턴 딜레이에서 차감해 관전 UX를 보존한다.

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 매치.
        topic: 토론 주제.
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        version_a: A측 에이전트 버전 스냅샷.
        version_b: B측 에이전트 버전 스냅샷.
        api_key_a: A측 LLM API 키.
        api_key_b: B측 LLM API 키.
        claims_a: A측 발언 누적 목록 (in-out 참조).
        claims_b: B측 발언 누적 목록 (in-out 참조).
        model_cache: LLMModel 캐시 dict.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.

    Returns:
        (total_penalty_a, total_penalty_b) 누적 벌점 튜플.

    Raises:
        ForfeitError: A 또는 B 발언이 모든 재시도 후에도 실패한 경우.
    """
    total_penalty_a = 0
    total_penalty_b = 0
    prev_evidence_a: str | None = None
    prev_evidence_b: str | None = None
    consecutive_severe_a = 0
    consecutive_severe_b = 0
    accumulated_violations_a: dict[str, int] = {}
    accumulated_violations_b: dict[str, int] = {}

    for turn_num in range(1, topic.max_turns + 1):
        # Agent A 턴
        turn_a = await executor.execute_with_retry(
            match, topic, turn_num, "agent_a",
            agent_a, version_a, api_key_a, claims_a, claims_b,
            my_accumulated_penalty=total_penalty_a,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
            prev_evidence=prev_evidence_a,
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
                trace_id=control_plane.runtime.trace_id if control_plane else None,
                orchestration_mode=control_plane.runtime.mode if control_plane else None,
                tools_available=(
                    settings.debate_tool_use_enabled and topic.tools_enabled and agent_a.provider in _TOOL_USE_PROVIDERS
                ),
                tool_result=(turn_a.raw_response or {}).get("tool_result"),
                debater_position="A (찬성)",
                opponent_recent_history=claims_b[-2:] if claims_b else None,
                max_turns=topic.max_turns,
                accumulated_violations=accumulated_violations_a,
            )
            review_elapsed = time.monotonic() - review_start

            total_penalty_a = _apply_review_to_turn(
                turn_a, review_a, claims_a, total_penalty_a, update_last_claim=False
            )
            if _has_severe_violation(review_a):
                consecutive_severe_a += 1
            else:
                consecutive_severe_a = 0
            _update_accumulated_violations(accumulated_violations_a, review_a)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_a >= _streak:
                raise ForfeitError(forfeited_speaker="agent_a")
            await _log_orchestrator_usage(
                db, agent_a.owner_id, review_a.get("model_id", ""),
                review_a["input_tokens"], review_a["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
        else:
            review_a = None
            review_elapsed = 0.0
            claims_a.append(turn_a.claim)

        await _publish_turn_event(
            str(match.id),
            turn_a,
            turn_a.review_result,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a") if control_plane else None,
        )
        if review_a is not None:
            fallback_reason = review_a.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=turn_num,
                    speaker="agent_a",
                )
            await _publish_review_event(
                str(match.id),
                turn_num,
                "agent_a",
                review_a,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_a", fallback_reason=fallback_reason)
                if control_plane else None,
                fallback_reason=fallback_reason,
            )

        # 관전 UX: 딜레이에서 검토 소요시간 차감
        remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)

        # A evidence 저장 (sequential 모드에서는 review 전 evidence가 없으나, 다음 턴 주입용으로 현 값 저장)
        prev_evidence_a = turn_a.evidence

        # Agent B 턴
        turn_b = await executor.execute_with_retry(
            match, topic, turn_num, "agent_b",
            agent_b, version_b, api_key_b, claims_b, claims_a,
            my_accumulated_penalty=total_penalty_b,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
            prev_evidence=prev_evidence_b,
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
                trace_id=control_plane.runtime.trace_id if control_plane else None,
                orchestration_mode=control_plane.runtime.mode if control_plane else None,
                tools_available=(
                    settings.debate_tool_use_enabled and topic.tools_enabled and agent_b.provider in _TOOL_USE_PROVIDERS
                ),
                tool_result=(turn_b.raw_response or {}).get("tool_result"),
                debater_position="B (반대)",
                opponent_recent_history=claims_a[-2:] if claims_a else None,
                max_turns=topic.max_turns,
                accumulated_violations=accumulated_violations_b,
            )
            review_elapsed = time.monotonic() - review_start

            total_penalty_b = _apply_review_to_turn(
                turn_b, review_b, claims_b, total_penalty_b, update_last_claim=False
            )
            if _has_severe_violation(review_b):
                consecutive_severe_b += 1
            else:
                consecutive_severe_b = 0
            _update_accumulated_violations(accumulated_violations_b, review_b)
            _streak = settings.debate_forfeit_on_severe_streak
            if _streak and consecutive_severe_b >= _streak:
                raise ForfeitError(forfeited_speaker="agent_b")
            await _log_orchestrator_usage(
                db, agent_b.owner_id, review_b.get("model_id", ""),
                review_b["input_tokens"], review_b["output_tokens"],
                model_cache=model_cache, usage_batch=usage_batch,
            )
        else:
            review_b = None
            review_elapsed = 0.0
            claims_b.append(turn_b.claim)

        await _publish_turn_event(
            str(match.id),
            turn_b,
            turn_b.review_result,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b") if control_plane else None,
        )
        if review_b is not None:
            fallback_reason = review_b.get("fallback_reason")
            if control_plane and fallback_reason:
                control_plane.mark_fallback(
                    fallback_reason,
                    stage="review",
                    turn_number=turn_num,
                    speaker="agent_b",
                )
            await _publish_review_event(
                str(match.id),
                turn_num,
                "agent_b",
                review_b,
                event_meta=control_plane.event_meta(turn_number=turn_num, speaker="agent_b", fallback_reason=fallback_reason)
                if control_plane else None,
                fallback_reason=fallback_reason,
            )

        # B evidence 저장 — 다음 턴 B 시스템 프롬프트 주입용
        prev_evidence_b = turn_b.evidence

        # 라운드 사이 딜레이 (마지막 제외)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    return total_penalty_a, total_penalty_b


# ── 멀티에이전트 슬롯 단일 턴 헬퍼 ───────────────────────────────────────────

async def _run_multi_slot_turn(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    turn_num: int,
    speaker_role: str,
    speaker_label: str,
    agent: DebateAgent,
    version: DebateAgentVersion | None,
    api_key: str,
    my_claims: list[str],
    opp_claims: list[str],
    total_penalty: int,
    model_cache: dict,
    usage_batch: list,
    control_plane: "OrchestrationControlPlane | None" = None,
    accumulated_violations: dict[str, int] | None = None,
) -> tuple[int, dict | None]:
    """멀티에이전트 슬롯 단일 턴: 실행 → 검토 → 이벤트 발행.

    agent_a/b 처리 블록의 중복 제거를 위해 추출. run_turns_multi() 루프 내에서
    speaker_role("agent_a"|"agent_b")과 speaker_label("agent_a_slot0" 등)을 분리해
    1v1과 동일한 이벤트 형식으로 발행한다.

    Returns:
        (total_penalty, review_result) — review_result는 LLM 검토 비활성 시 None.
    """
    turn = await executor.execute_with_retry(
        match, topic, turn_num, speaker_role,
        agent, version, api_key, my_claims, opp_claims,
        my_accumulated_penalty=total_penalty,
        event_meta=control_plane.event_meta(turn_number=turn_num, speaker=speaker_label) if control_plane else None,
    )
    if turn is None:
        raise ForfeitError(forfeited_speaker=speaker_role)
    total_penalty += turn.penalty_total

    if settings.debate_turn_review_enabled:
        review = await orchestrator.review_turn(
            topic=topic.title,
            speaker=speaker_label,
            turn_number=turn_num,
            claim=turn.claim,
            evidence=turn.evidence,
            action=turn.action,
            opponent_last_claim=opp_claims[-1] if opp_claims else None,
            recent_history=my_claims[-2:] if my_claims else None,
            trace_id=control_plane.runtime.trace_id if control_plane else None,
            orchestration_mode=control_plane.runtime.mode if control_plane else None,
            tools_available=(
                settings.debate_tool_use_enabled and topic.tools_enabled and agent.provider in _TOOL_USE_PROVIDERS
            ),
            tool_result=(turn.raw_response or {}).get("tool_raw_content") or (turn.raw_response or {}).get("tool_result"),
            debater_position=speaker_role.replace("agent_", "").upper() + " 측",
            opponent_recent_history=opp_claims[-2:] if opp_claims else None,
            max_turns=topic.max_turns,
            accumulated_violations=accumulated_violations,
        )
        total_penalty = _apply_review_to_turn(
            turn, review, my_claims, total_penalty, update_last_claim=False
        )
        await _log_orchestrator_usage(
            db, agent.owner_id, review.get("model_id", ""),
            review["input_tokens"], review["output_tokens"],
            model_cache=model_cache, usage_batch=usage_batch,
        )
        fallback_reason = review.get("fallback_reason")
        if control_plane and fallback_reason:
            control_plane.mark_fallback(
                fallback_reason,
                stage="review",
                turn_number=turn_num,
                speaker=speaker_label,
            )
        await _publish_review_event(
            str(match.id),
            turn_num,
            speaker_label,
            review,
            event_meta=control_plane.event_meta(turn_number=turn_num, speaker=speaker_label, fallback_reason=fallback_reason)
            if control_plane else None,
            fallback_reason=fallback_reason,
        )
        review_returned = review
    else:
        my_claims.append(turn.claim)
        review_returned = None

    # turn.speaker는 "agent_a"|"agent_b"이므로 슬롯 레이블로 오버라이드
    await _publish_turn_event(
        str(match.id),
        turn,
        turn.review_result,
        event_meta=control_plane.event_meta(turn_number=turn_num, speaker=speaker_label) if control_plane else None,
    )
    # 슬롯 레이블을 별도 필드로 보완 (프론트엔드 멀티에이전트 구분용)
    slot_payload = {"speaker": speaker_label, "turn_number": turn_num}
    if control_plane:
        slot_payload.update(control_plane.event_meta(turn_number=turn_num, speaker=speaker_label))
    await publish_event(str(match.id), "turn_slot", slot_payload)

    return total_penalty, review_returned


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
    control_plane: "OrchestrationControlPlane | None" = None,
) -> TurnLoopResult:
    """멀티에이전트 턴 루프 (2v2/3v3 라운드 로빈).

    DebateMatchParticipant를 team A/B로 분류한 뒤 슬롯 인덱스를 라운드 로빈으로 순환.
    슬롯 수가 팀 간 다를 경우 짧은 팀은 mod 연산으로 순환 재사용된다.
    에이전트·버전은 루프 진입 전 한 번에 배치 조회해 반복 DB SELECT를 방지한다.

    Args:
        executor: 단일 턴 실행기.
        orchestrator: LLM 검토 오케스트레이터.
        db: 비동기 DB 세션.
        match: 실행 중인 멀티에이전트 매치.
        topic: 토론 주제.
        agent_a: 대표 A측 에이전트 (ELO·판정용, 실제 발언은 participants 기반).
        agent_b: 대표 B측 에이전트 (ELO·판정용, 실제 발언은 participants 기반).
        model_cache: LLMModel 캐시 dict.
        usage_batch: 배치 INSERT용 TokenUsageLog 목록.

    Returns:
        TurnLoopResult: 발언 목록·누적 벌점·캐시 등 턴 루프 집계 결과.

    Raises:
        ForfeitError: 슬롯 에이전트 발언이 모든 재시도 후에도 실패한 경우.
    """
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
    accumulated_violations_a: dict[str, int] = {}
    accumulated_violations_b: dict[str, int] = {}
    consecutive_severe_a = 0
    consecutive_severe_b = 0

    for turn_num in range(1, topic.max_turns + 1):
        for i in range(max_slots):
            a_part = team_a[i % len(team_a)]
            b_part = team_b[i % len(team_b)]

            multi_agent_a = agents_cache.get(str(a_part.agent_id))
            multi_agent_b = agents_cache.get(str(b_part.agent_id))

            if multi_agent_a is None or multi_agent_b is None:
                logger.warning("Multi-agent: agent not found, slot %d turn %d", i, turn_num)
                continue

            api_key_a = _resolve_api_key(multi_agent_a)
            api_key_b = _resolve_api_key(multi_agent_b)

            ver_a = versions_cache.get(str(a_part.version_id)) if a_part.version_id else None
            ver_b = versions_cache.get(str(b_part.version_id)) if b_part.version_id else None

            total_penalty_a, review_a = await _run_multi_slot_turn(
                executor, orchestrator, db, match, topic, turn_num,
                "agent_a", f"agent_a_slot{i}",
                multi_agent_a, ver_a, api_key_a, claims_a, claims_b,
                total_penalty_a, model_cache, usage_batch, control_plane=control_plane,
                accumulated_violations=accumulated_violations_a,
            )
            if review_a is not None:
                if _has_severe_violation(review_a):
                    consecutive_severe_a += 1
                else:
                    consecutive_severe_a = 0
                _update_accumulated_violations(accumulated_violations_a, review_a)
                _streak = settings.debate_forfeit_on_severe_streak
                if _streak and consecutive_severe_a >= _streak:
                    raise ForfeitError(forfeited_speaker="agent_a")

            total_penalty_b, review_b = await _run_multi_slot_turn(
                executor, orchestrator, db, match, topic, turn_num,
                "agent_b", f"agent_b_slot{i}",
                multi_agent_b, ver_b, api_key_b, claims_b, claims_a,
                total_penalty_b, model_cache, usage_batch, control_plane=control_plane,
                accumulated_violations=accumulated_violations_b,
            )
            if review_b is not None:
                if _has_severe_violation(review_b):
                    consecutive_severe_b += 1
                else:
                    consecutive_severe_b = 0
                _update_accumulated_violations(accumulated_violations_b, review_b)
                _streak = settings.debate_forfeit_on_severe_streak
                if _streak and consecutive_severe_b >= _streak:
                    raise ForfeitError(forfeited_speaker="agent_b")

    return TurnLoopResult(claims_a, claims_b, total_penalty_a, total_penalty_b, model_cache, usage_batch)


# ── 포맷 dispatch ──────────────────────────────────────────────────────────────

# 새 형식 추가 = 함수 1개 + 이 dict 1줄
_FORMAT_RUNNERS: dict[str, Callable] = {
    "1v1": run_turns_1v1,
    "2v2": run_turns_multi,
    "3v3": run_turns_multi,
}


def get_format_runner(match_format: str) -> Callable:
    """매치 포맷에 대응하는 턴 루프 함수를 반환한다.

    등록되지 않은 포맷은 run_turns_1v1로 폴백한다.

    Args:
        match_format: 매치 포맷 문자열 ('1v1' | '2v2' | '3v3').

    Returns:
        대응하는 턴 루프 코루틴 함수.
    """
    return _FORMAT_RUNNERS.get(match_format, run_turns_1v1)
