"""토론 엔진. 비동기 백그라운드 태스크로 매치를 실행."""

import asyncio
import contextlib
import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # create_async_engine: 독립 세션용

from app.core.config import settings
from app.core.encryption import decrypt_api_key
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User
from app.schemas.debate_ws import WSMatchReady, WSTurnRequest
from app.services.debate.agent_service import DebateAgentService
from app.services.debate.broadcast import publish_event
from app.services.debate.orchestrator import DebateOrchestrator, calculate_elo
from app.services.debate.tool_executor import AVAILABLE_TOOLS, DebateToolExecutor, ToolContext
from app.services.debate.ws_manager import WSConnectionManager
from app.services.llm.inference_client import InferenceClient

logger = logging.getLogger(__name__)


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


# 에이전트 LLM에 주입하는 응답 형식 지시문 — _execute_turn() 내 user 메시지 끝에 추가됨
# 에이전트가 임의 텍스트 대신 구조화 JSON을 반환하도록 강제.
# validate_response_schema()가 이 형식을 검증하며, 불일치 시 파싱 실패로 처리.
RESPONSE_SCHEMA_INSTRUCTION = """⚠️ 중요: 반드시 한국어로만 답변하세요. 영어 사용 금지.

다음 형식의 JSON만 응답하세요 (다른 텍스트 없이):
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<한국어로 작성한 주요 주장>",
  "evidence": "<한국어로 작성한 근거/데이터/인용>" | null,
  "tool_used": null,
  "tool_result": null
}

action 선택 기준 (상황에 맞는 전략을 자유롭게 선택하세요):
- "argue"  : 새로운 주장이나 추가 근거를 제시할 때
- "rebut"  : 상대방의 구체적 논거·데이터를 직접 논리적으로 반박할 때
- "question": 상대방 주장의 전제·근거에 의문을 제기하거나 약점을 파고들 때
- "concede": 상대방 논거 중 타당한 부분을 인정하되 자신의 핵심 입장은 유지할 때
- "summarize": 논점을 정리하거나 마무리 단계에서 핵심을 압축할 때"""

# 코드 기반 벌점 — LLM 검토 이전에 즉시 적용 (debate_engine 단독 처리)
# LLM 기반 벌점은 debate_orchestrator.LLM_VIOLATION_PENALTIES 참조
PENALTY_REPETITION = 3         # detect_repetition()이 단어 중복 70%+ 감지 시 부여
PENALTY_FALSE_SOURCE = 7       # tool_result를 실제 도구 호출 없이 허위로 반환한 경우


class ForfeitError(Exception):
    """재시도를 모두 소진한 에이전트의 부전패를 알리는 예외."""

    def __init__(self, forfeited_speaker: str) -> None:
        self.forfeited_speaker = forfeited_speaker
        super().__init__(f"Forfeit by {forfeited_speaker}")


def detect_repetition(new_claim: str, previous_claims: list[str], threshold: float = 0.7) -> bool:
    """단순 단어 집합 유사도로 동어반복 감지.

    overlap / max(len_new, len_prev) >= threshold(0.7)이면 반복 판정.
    공백 분리 단어 기준이므로 어휘 수준 비교만 수행 (의미적 유사도 미포함).
    허용 오탐율을 고려해 threshold를 0.7로 설정 — 0.6이면 정상 발언도 자주 차단됨.
    """
    # 비교 대상이 없으면 반복으로 볼 수 없음 — 첫 번째 발언은 항상 통과
    if not previous_claims:
        return False
    new_words = set(new_claim.lower().split())
    # 빈 발언은 단어가 없으므로 유사도 계산 불가 — 반복 판정 제외
    if not new_words:
        return False
    # 모든 이전 발언과 비교해 하나라도 threshold를 초과하면 즉시 반복 판정
    for prev in previous_claims:
        prev_words = set(prev.lower().split())
        # 이전 발언이 비어있으면 분모가 0이 되므로 스킵
        if not prev_words:
            continue
        overlap = len(new_words & prev_words)
        similarity = overlap / max(len(new_words), len(prev_words))
        if similarity >= threshold:
            return True
    return False


def validate_response_schema(response_text: str) -> dict | None:
    """응답 JSON 파싱 및 스키마 검증. 유효하면 dict, 아니면 None."""
    text = response_text.strip()

    # 1단계: 마크다운 코드블록 제거
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```", "", text).strip()

    # 2단계: JSON 파싱 시도 (전체 텍스트가 JSON인 경우)
    data = None
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        data = json.loads(text)

    # 3단계: 텍스트 중간에 JSON이 포함된 경우 추출
    if data is None:
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                data = json.loads(json_match.group(0))

    if data is None:
        return None

    required_keys = {"action", "claim"}
    # action과 claim은 에이전트 발언의 필수 필드 — 하나라도 없으면 턴 처리 불가
    if not required_keys.issubset(data.keys()):
        return None

    valid_actions = {"argue", "rebut", "concede", "question", "summarize"}
    # RESPONSE_SCHEMA_INSTRUCTION에 정의된 5개 액션만 허용 — 임의 값 거부
    if data.get("action") not in valid_actions:
        return None

    # claim이 비어있으면 실패
    if not str(data.get("claim", "")).strip():
        return None

    # tool_used, tool_result, evidence 기본값 보장
    data.setdefault("evidence", None)
    data.setdefault("tool_used", None)
    data.setdefault("tool_result", None)

    return data


def _resolve_api_key(agent: DebateAgent, force_platform: bool = False) -> str:
    """에이전트 API 키 반환. 우선순위: BYOK 복호화 → 플랫폼 환경변수 → 빈 문자열.

    force_platform=True이면 BYOK를 무시하고 플랫폼 환경변수 키를 직접 사용.
    테스트 매치(is_test=True)에서 호출 시 항상 True로 전달됨.
    """
    if agent.provider == "local":
        return ""

    # 플랫폼 강제 모드 (테스트 매치 또는 platform credits 에이전트)
    if force_platform or getattr(agent, "use_platform_credits", False):
        match agent.provider:
            case "openai":
                return settings.openai_api_key or ""
            case "anthropic":
                return settings.anthropic_api_key or ""
            case "google":
                return settings.google_api_key or ""
            case "runpod":
                return settings.runpod_api_key or ""
            case _:
                return ""

    # BYOK 키가 설정돼 있으면 복호화 시도
    if agent.encrypted_api_key:
        try:
            return decrypt_api_key(agent.encrypted_api_key)
        except ValueError:
            # 키 불일치(SECRET_KEY 변경 등) → 플랫폼 키로 폴백
            logger.warning(
                "Agent %s API key decrypt failed, falling back to platform key", agent.id
            )

    # 플랫폼 기본 API 키 폴백
    match agent.provider:
        case "openai":
            return settings.openai_api_key or ""
        case "anthropic":
            return settings.anthropic_api_key or ""
        case "google":
            return settings.google_api_key or ""
        case "runpod":
            return settings.runpod_api_key or ""
        case _:
            return ""


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


# ── 몰수패 처리 ───────────────────────────────────────────────────────────────

async def _settle_forfeit(
    db: AsyncSession,
    match: DebateMatch,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    elo_result: str,
    result_a: str,
    result_b: str,
    version_a_id: str | None = None,
    version_b_id: str | None = None,
) -> tuple[float, float]:
    """부전패 공통 후처리: ELO + 에이전트 전적 갱신 + 시즌 ELO + 승급전 결과 반영.

    is_test=True이면 모든 갱신을 건너뜀.
    Returns: (new_a_elo, new_b_elo)
    """
    from app.services.debate.promotion_service import DebatePromotionService
    from app.services.debate.season_service import DebateSeasonService

    new_a, new_b = calculate_elo(
        agent_a.elo_rating, agent_b.elo_rating, elo_result,
        score_diff=settings.debate_elo_forfeit_score_diff,
    )

    if match.is_test:
        return new_a, new_b

    agent_service = DebateAgentService(db)
    await agent_service.update_elo(str(agent_a.id), new_a, result_a, version_a_id)
    await agent_service.update_elo(str(agent_b.id), new_b, result_b, version_b_id)

    if match.season_id:
        season_svc = DebateSeasonService(db)
        stats_a = await season_svc.get_or_create_season_stats(str(agent_a.id), str(match.season_id))
        stats_b = await season_svc.get_or_create_season_stats(str(agent_b.id), str(match.season_id))
        s_new_a, s_new_b = calculate_elo(
            stats_a.elo_rating, stats_b.elo_rating, elo_result,
            score_diff=settings.debate_elo_forfeit_score_diff,
        )
        await season_svc.update_season_stats(str(agent_a.id), str(match.season_id), s_new_a, result_a)
        await season_svc.update_season_stats(str(agent_b.id), str(match.season_id), s_new_b, result_b)

    promo_svc = DebatePromotionService(db)
    for agent_obj, res in [(agent_a, result_a), (agent_b, result_b)]:
        active = await promo_svc.get_active_series(str(agent_obj.id))
        if active:
            series_result = await promo_svc.record_match_result(str(active.id), res)
            await publish_event(str(match.id), "series_update", series_result)

    return new_a, new_b


async def _handle_forfeit(
    db: AsyncSession,
    match: DebateMatch,
    loser_agent: DebateAgent,
    winner_agent: DebateAgent,
    side: str,  # "agent_a" or "agent_b"
) -> None:
    """몰수패 처리 — 상태 갱신, ELO 계산, 이벤트 발행."""
    match.status = "forfeit"
    match.finished_at = datetime.now(UTC)
    match.winner_id = winner_agent.id
    await db.commit()

    if side == "agent_a":
        agent_a_obj, agent_b_obj = loser_agent, winner_agent
        elo_result, result_a, result_b = "b_win", "loss", "win"
    else:
        agent_a_obj, agent_b_obj = winner_agent, loser_agent
        elo_result, result_a, result_b = "a_win", "win", "loss"

    version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
    version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None

    await _settle_forfeit(
        db, match, agent_a_obj, agent_b_obj, elo_result, result_a, result_b,
        version_a_id, version_b_id,
    )

    await db.commit()
    await publish_event(str(match.id), "forfeit", {
        "match_id": str(match.id),
        "reason": f"Agent {loser_agent.name} did not connect in time",
        "winner_id": str(winner_agent.id),
    })
    logger.info("Match %s forfeit: agent %s did not connect", match.id, loser_agent.name)


# ── 판정 후처리 ───────────────────────────────────────────────────────────────

async def _finalize_forfeit(
    db: AsyncSession,
    match: DebateMatch,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    forfeited_speaker: str,
) -> None:
    """재시도 소진으로 인한 부전패 처리. judge() 없이 바로 매치를 종료한다.

    부전패 에이전트에게 점수 0, 상대방에게 점수 100 부여.
    ELO는 최대 점수차(100)로 계산한다.
    """
    from app.services.debate.match_service import DebateMatchService

    if forfeited_speaker == "agent_a":
        forfeit_winner, forfeit_loser = agent_b, agent_a
        score_a, score_b = 0, 100
        elo_result, result_a, result_b = "b_win", "loss", "win"
    else:
        forfeit_winner, forfeit_loser = agent_a, agent_b
        score_a, score_b = 100, 0
        elo_result, result_a, result_b = "a_win", "win", "loss"

    elo_a_before = agent_a.elo_rating
    elo_b_before = agent_b.elo_rating

    match.status = "completed"
    match.finished_at = datetime.now(UTC)
    match.winner_id = forfeit_winner.id
    match.score_a = score_a
    match.score_b = score_b

    version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
    version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None

    new_a, new_b = await _settle_forfeit(
        db, match, agent_a, agent_b, elo_result, result_a, result_b,
        version_a_id, version_b_id,
    )

    await db.execute(
        update(DebateMatch)
        .where(DebateMatch.id == match.id)
        .values(elo_a_before=elo_a_before, elo_b_before=elo_b_before, elo_a_after=new_a, elo_b_after=new_b)
    )
    await db.commit()

    await publish_event(str(match.id), "forfeit", {
        "forfeited_speaker": forfeited_speaker,
        "winner_id": str(forfeit_winner.id),
        "loser_id": str(forfeit_loser.id),
        "reason": "Turn execution failed after all retries",
    })

    await publish_event(str(match.id), "finished", {
        "winner_id": str(forfeit_winner.id),
        "score_a": score_a,
        "score_b": score_b,
        "elo_a_before": elo_a_before,
        "elo_a_after": new_a,
        "elo_b_before": elo_b_before,
        "elo_b_after": new_b,
        # 하위 호환: 기존 필드명도 함께 포함
        "elo_a": new_a,
        "elo_b": new_b,
    })

    match_service = DebateMatchService(db)
    await match_service.resolve_predictions(
        str(match.id),
        str(forfeit_winner.id),
        str(match.agent_a_id),
        str(match.agent_b_id),
    )

    logger.info(
        "Match %s ended by forfeit. %s failed after retries, winner: %s",
        match.id, forfeit_loser.name, forfeit_winner.name,
    )


async def _finalize_match(
    db: AsyncSession,
    match: DebateMatch,
    judgment: dict,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    orchestrator: DebateOrchestrator,
    model_cache: dict,
    usage_batch: list,
) -> None:
    """판정 결과를 DB에 저장하고 후속 처리를 순서대로 실행한다.

    처리 순서:
      1. Judge LLM 토큰 사용량 기록 (usage_batch 추가)
      2. ELO 계산 → 에이전트 전적·레이팅 갱신 (update_elo)
      3. 시즌 ELO 분리 갱신 (match.season_id가 있을 때만)
      4. 승급전/강등전 결과 반영 (DebatePromotionService.record_match_result)
      5. "finished" SSE 이벤트 발행 (ELO 변동 전후값 포함)
      6. DB 커밋 + usage_batch 일괄 INSERT
      7. 예측투표 정산 (resolve_predictions)
      8. 토너먼트 라운드 진행 (tournament_id가 있을 때만)
      9. 요약 리포트 생성 (백그라운드 asyncio 태스크)

    is_test=True 매치는 ELO·시즌·승급전 갱신을 건너뛴다.
    """
    from app.services.debate.match_service import DebateMatchService, generate_summary_task
    from app.services.debate.promotion_service import DebatePromotionService
    from app.services.debate.season_service import DebateSeasonService

    # 판정 오케스트레이터 토큰 로깅
    await _log_orchestrator_usage(
        db, agent_a.owner_id, judgment.get("model_id", ""),
        judgment["input_tokens"], judgment["output_tokens"],
        model_cache=model_cache, usage_batch=usage_batch,
    )

    # ELO 계산
    if judgment["winner_id"] == match.agent_a_id:
        elo_result = "a_win"
    elif judgment["winner_id"] == match.agent_b_id:
        elo_result = "b_win"
    else:
        elo_result = "draw"

    score_diff = abs(judgment["score_a"] - judgment["score_b"])
    elo_a_before = agent_a.elo_rating
    elo_b_before = agent_b.elo_rating
    new_a, new_b = calculate_elo(elo_a_before, elo_b_before, elo_result, score_diff=score_diff)

    match.scorecard = judgment["scorecard"]
    match.score_a = judgment["score_a"]
    match.score_b = judgment["score_b"]
    match.winner_id = judgment["winner_id"]
    match.status = "completed"
    match.finished_at = datetime.now(UTC)

    result_a = "win" if elo_result == "a_win" else ("loss" if elo_result == "b_win" else "draw")
    result_b = "win" if elo_result == "b_win" else ("loss" if elo_result == "a_win" else "draw")

    agent_service = DebateAgentService(db)
    if not match.is_test:
        await agent_service.update_elo(
            str(agent_a.id), new_a, result_a,
            str(match.agent_a_version_id) if match.agent_a_version_id else None,
        )
        await agent_service.update_elo(
            str(agent_b.id), new_b, result_b,
            str(match.agent_b_version_id) if match.agent_b_version_id else None,
        )

        if match.season_id:
            season_svc = DebateSeasonService(db)
            stats_a = await season_svc.get_or_create_season_stats(str(agent_a.id), str(match.season_id))
            stats_b = await season_svc.get_or_create_season_stats(str(agent_b.id), str(match.season_id))
            season_new_a, season_new_b = calculate_elo(
                stats_a.elo_rating, stats_b.elo_rating, elo_result, score_diff=score_diff
            )
            await season_svc.update_season_stats(str(agent_a.id), str(match.season_id), season_new_a, result_a)
            await season_svc.update_season_stats(str(agent_b.id), str(match.season_id), season_new_b, result_b)

        promo_svc = DebatePromotionService(db)
        series_updates: list[dict] = []
        # 양쪽 에이전트 각각 활성 승급전/강등전 시리즈 확인 후 결과 기록
        for agent_obj, res in [(agent_a, result_a), (agent_b, result_b)]:
            if res == "draw":
                # 승급전: 무승부 카운트 제외 (재도전), 강등전: 승리로 처리
                active = await promo_svc.get_active_series(str(agent_obj.id))
                # 강등전 무승부는 승리로 간주 — 1판 필승 규칙의 예외 처리
                if active and active.series_type == "demotion":
                    series_result = await promo_svc.record_match_result(str(active.id), "win")
                    series_updates.append(series_result)
                # 승급전 무승부는 기록하지 않음 — 재도전 기회 부여
            else:
                active = await promo_svc.get_active_series(str(agent_obj.id))
                # 활성 시리즈가 있는 경우에만 결과 기록 (일반 매치는 시리즈 없음)
                if active:
                    series_result = await promo_svc.record_match_result(str(active.id), res)
                    series_updates.append(series_result)

        for su in series_updates:
            await publish_event(str(match.id), "series_update", su)

    # 관전자에게 결과를 즉시 알림 — DB 커밋(ELO 저장)을 기다리지 않아 체감 지연 최소화
    await publish_event(str(match.id), "finished", {
        "winner_id": str(judgment["winner_id"]) if judgment["winner_id"] else None,
        "score_a": judgment["score_a"],
        "score_b": judgment["score_b"],
        "elo_a_before": elo_a_before,
        "elo_a_after": new_a,
        "elo_b_before": elo_b_before,
        "elo_b_after": new_b,
        # 하위 호환: 기존 필드명도 함께 포함
        "elo_a": new_a,
        "elo_b": new_b,
    })

    await db.execute(
        update(DebateMatch)
        .where(DebateMatch.id == match.id)
        .values(
            elo_a_before=elo_a_before,
            elo_b_before=elo_b_before,
            elo_a_after=new_a,
            elo_b_after=new_b,
        )
    )

    # 누적된 토큰 사용량 로그 일괄 INSERT
    if usage_batch:
        db.add_all(usage_batch)
    await db.commit()

    match_service = DebateMatchService(db)
    await match_service.resolve_predictions(
        str(match.id),
        str(match.winner_id) if match.winner_id else None,
        str(match.agent_a_id),
        str(match.agent_b_id),
    )

    if match.tournament_id:
        from app.services.debate.tournament_service import DebateTournamentService
        t_service = DebateTournamentService(db)
        await t_service.advance_round(str(match.tournament_id))

    if settings.debate_summary_enabled:
        asyncio.create_task(generate_summary_task(str(match.id)))

    logger.info("Match %s completed. Winner: %s", match.id, judgment["winner_id"])


# ── 턴 루프 ───────────────────────────────────────────────────────────────────

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
    """통합 턴 루프. parallel=True면 롤링 B 리뷰 + create_task 병렬 실행, False면 순차 실행.

    에이전트 발언이 재시도를 모두 소진하면 ForfeitError을 raise한다.
    """
    claims_a: list[str] = []
    claims_b: list[str] = []
    total_penalty_a = 0
    total_penalty_b = 0

    if parallel:
        # 롤링 병렬 패턴: B 리뷰를 백그라운드로 시작하고 다음 턴 A 실행 후 await
        # B 리뷰가 10-15초이므로 다음 턴 A 실행(동일 규모) 동안 숨겨져 순수 대기 없음
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
            turn_a = await _execute_turn_with_retry(
                db, client, match, topic, turn_num, "agent_a",
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
            # review_result는 gather 후 turn_review 이벤트로 별도 발행한다.
            await _publish_turn_event(str(match.id), turn_a, review_result=None)

            if settings.debate_turn_review_enabled:
                # A 검토를 백그라운드 태스크로 시작 — B 실행과 병렬로 진행
                # asyncio.gather 대신 create_task를 사용하면 B 실행 완료 즉시 B 이벤트를 발행할 수 있어
                # review 지연(~25s)이 B 스트리밍을 막지 않는다.
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
                turn_b = await _execute_turn_with_retry(
                    db, client, match, topic, turn_num, "agent_b",
                    agent_b, version_b, key_b, claims_b, claims_a,
                    my_accumulated_penalty=total_penalty_b,
                )
                if turn_b is None:
                    raise ForfeitError(forfeited_speaker="agent_b")
                total_penalty_b += turn_b.penalty_total

                # B 발언을 검토 전에 즉시 등록 — 다음 턴 A가 원본 클레임을 참조할 수 있도록
                # 리뷰에서 차단되면 루프 시작 시 claims_b[-1]을 blocked_claim으로 패치
                claims_b.append(turn_b.claim)

                # ★ B 턴 이벤트 즉시 발행 — A 검토 완료를 기다리지 않으므로 스트리밍 지연 없음
                await _publish_turn_event(str(match.id), turn_b, review_result=None)

                # ★ B 리뷰를 백그라운드 태스크로 시작 — 다음 턴 A 실행과 병렬로 진행
                # B 리뷰(LLM 호출만, DB 접근 없음)는 asyncio 단일 스레드에서 안전
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
                # 리뷰 비활성: B 순차 실행. B 실행 시간을 딜레이에서 차감해 review-enabled와 동일한 속도 보장
                b_exec_start = time.monotonic()
                turn_b = await _execute_turn_with_retry(
                    db, client, match, topic, turn_num, "agent_b",
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
        # 마지막 턴의 B 리뷰는 루프 내에서 await할 다음 턴이 없으므로 여기서 처리
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

    else:

        for turn_num in range(1, topic.max_turns + 1):
            # Agent A 턴
            turn_a = await _execute_turn_with_retry(
                db, client, match, topic, turn_num, "agent_a",
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
            turn_b = await _execute_turn_with_retry(
                db, client, match, topic, turn_num, "agent_b",
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

    return claims_a, claims_b, total_penalty_a, total_penalty_b


# ── 매치 실행 진입점 ──────────────────────────────────────────────────────────

async def run_debate(match_id: str) -> None:
    """매치 실행. 독립 DB 세션으로 백그라운드 실행."""
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as notify_db:
        try:
            from app.services.notification_service import NotificationService
            await NotificationService(notify_db).notify_match_event(match_id, "match_started")
            await notify_db.commit()
        except Exception:
            logger.warning("Start notification failed for match %s", match_id, exc_info=True)

    async with session_factory() as db:
        try:
            await _execute_match(db, match_id)
        except asyncio.CancelledError:
            # 서버 재시작/태스크 취소 — asyncio.shield로 DB 정리 후 재발생
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
            # 정상 완료 후 매치 종료 알림 — 핵심 경로 세션과 별도 세션 사용
            async with session_factory() as notify_db:
                try:
                    from app.services.notification_service import NotificationService
                    await NotificationService(notify_db).notify_match_event(match_id, "match_finished")
                    await notify_db.commit()
                except Exception:
                    logger.warning("Finish notification failed for match %s", match_id, exc_info=True)
        finally:
            await engine.dispose()


async def _execute_match(db: AsyncSession, match_id: str) -> None:
    """턴 루프 + 판정 + ELO 갱신."""
    # 매치 로드
    result = await db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
    match = result.scalar_one_or_none()
    if match is None:
        raise ValueError(f"Match {match_id} not found")

    # 토픽 로드
    topic_result = await db.execute(select(DebateTopic).where(DebateTopic.id == match.topic_id))
    topic = topic_result.scalar_one()

    # 에이전트 배치 조회 — A/B 개별 SELECT 대신 단일 IN 쿼리
    agents_res = await db.execute(
        select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
    )
    agents_map = {str(a.id): a for a in agents_res.scalars().all()}
    agent_a = agents_map[str(match.agent_a_id)]
    agent_b = agents_map[str(match.agent_b_id)]

    # 버전 배치 조회 — None인 경우를 제외한 버전 ID만 조회
    version_ids = [v for v in [match.agent_a_version_id, match.agent_b_version_id] if v is not None]
    versions_map: dict = {}
    if version_ids:
        versions_res = await db.execute(
            select(DebateAgentVersion).where(DebateAgentVersion.id.in_(version_ids))
        )
        versions_map = {str(v.id): v for v in versions_res.scalars().all()}
    version_a = versions_map.get(str(match.agent_a_version_id)) if match.agent_a_version_id else None
    version_b = versions_map.get(str(match.agent_b_version_id)) if match.agent_b_version_id else None

    # 로컬 에이전트 접속 대기
    ws_manager = WSConnectionManager.get_instance()
    has_local = agent_a.provider == "local" or agent_b.provider == "local"

    if has_local:
        match.status = "waiting_agent"
        await db.commit()
        await publish_event(str(match.id), "waiting_agent", {"match_id": str(match.id)})

        for agent, side in [(agent_a, "agent_a"), (agent_b, "agent_b")]:
            if agent.provider == "local":
                connected = await ws_manager.wait_for_connection(
                    agent.id, settings.debate_agent_connect_timeout
                )
                if not connected:
                    winner_agent = agent_b if side == "agent_a" else agent_a
                    await _handle_forfeit(db, match, agent, winner_agent, side)
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

    # 크레딧 차감 (debate_credit_cost > 0이고 크레딧 시스템이 활성화된 경우)
    # BYOK 에이전트(자기 API 키 사용)는 차감 제외 — 플랫폼 키 사용 에이전트만 차감
    # join_queue에서 사전 검증을 거쳤지만 race condition 대비 이중 체크
    if settings.debate_credit_cost > 0 and settings.credit_system_enabled:
        for agent in (agent_a, agent_b):
            if agent.encrypted_api_key:
                continue
            deduct_result = await db.execute(
                update(User)
                .where(User.id == agent.owner_id, User.credit_balance >= settings.debate_credit_cost)
                .values(credit_balance=User.credit_balance - settings.debate_credit_cost)
                .returning(User.credit_balance)
            )
            row = deduct_result.fetchone()
            if row is None:
                # join_queue 사전 검증을 통과했지만 race condition으로 잔액 부족 → 예외 발생시켜 error 처리
                raise ValueError(
                    f"에이전트 '{agent.name}' 소유자의 크레딧이 부족합니다 (필요: {settings.debate_credit_cost}석)"
                )

        await db.commit()

    # API 키 복호화 — 테스트 매치는 항상 플랫폼 키 사용 (소유자 키 미사용)
    use_platform = getattr(match, "is_test", False)
    key_a = _resolve_api_key(agent_a, force_platform=use_platform)
    key_b = _resolve_api_key(agent_b, force_platform=use_platform)

    # 매치 시작
    match.status = "in_progress"
    match.started_at = datetime.now(UTC)
    await db.commit()

    await publish_event(str(match.id), "started", {"match_id": str(match.id)})

    # async with으로 InferenceClient를 사용해 예외·조기 반환 시에도 HTTP 연결 풀이 정리됨
    async with InferenceClient() as client:
        await _run_match_with_client(db, match, topic, agent_a, agent_b, version_a, version_b, key_a, key_b, client)


async def _run_match_with_client(
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
) -> None:
    """InferenceClient를 인자로 받아 턴 루프 + 판정을 실행. _execute_match에서 async with 블록 내에서 호출."""
    # 엔진의 InferenceClient 커넥션 풀을 재사용 — 오케스트레이터 전용 httpx 클라이언트 생성 방지
    orchestrator = DebateOrchestrator(optimized=settings.debate_orchestrator_optimized, client=client)

    # LLMModel 조회 캐시 (모델 ID → LLMModel 객체) — 반복 SELECT 방지
    model_cache: dict[str, LLMModel] = {}
    # TokenUsageLog 배치 — 매치 종료 시 일괄 INSERT
    usage_batch: list[TokenUsageLog] = []

    # 멀티 에이전트 포맷 분기 — 1v1이 아닌 경우 _execute_multi_and_finalize로 위임 후 반환
    match_format = getattr(match, "format", "1v1")
    if match_format != "1v1":
        await _execute_multi_and_finalize(
            match, topic, db, client, orchestrator, agent_a, agent_b
        )
        return

    try:
        claims_a, claims_b, total_penalty_a, total_penalty_b = await _run_turn_loop(
            db, match, topic, agent_a, agent_b, version_a, version_b,
            key_a, key_b, client, orchestrator, model_cache, usage_batch,
            parallel=orchestrator.optimized,
        )
    except ForfeitError as forfeit:
        await _finalize_forfeit(db, match, agent_a, agent_b, forfeit.forfeited_speaker)
        return

    match.penalty_a = total_penalty_a
    match.penalty_b = total_penalty_b
    await db.commit()

    turns = await _load_turns(db, match.id)
    judgment = await orchestrator.judge(
        match, turns, topic, agent_a_name=agent_a.name, agent_b_name=agent_b.name
    )

    await _finalize_match(
        db, match, judgment, agent_a, agent_b,
        orchestrator, model_cache, usage_batch,
    )


async def _execute_turn(
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
) -> DebateTurnLog:
    """단일 턴 실행. 벌점 감지 포함."""
    default_prompt = "당신은 한국어 토론 참가자입니다. 반드시 한국어로만 답변하세요."
    system_prompt = version.system_prompt if version else default_prompt

    penalties: dict[str, int] = {}
    penalty_total = 0
    action = "argue"
    claim = ""
    evidence = None
    raw_response = None
    input_tokens = 0
    output_tokens = 0
    response_time_ms: int | None = None

    try:
        if agent.provider == "local":
            # WebSocket 경유 턴 요청 — 응답 시간 측정
            ws_manager = WSConnectionManager.get_instance()
            ws_request = WSTurnRequest(
                match_id=match.id,
                turn_number=turn_number,
                speaker=speaker,
                topic_title=topic.title,
                topic_description=topic.description,
                max_turns=topic.max_turns,
                turn_token_limit=topic.turn_token_limit,
                my_previous_claims=my_claims,
                opponent_previous_claims=opponent_claims,
                time_limit_seconds=settings.debate_turn_timeout_seconds,
                # tools_enabled=False이면 빈 목록 전달 → 에이전트가 툴 사용 불가
                available_tools=AVAILABLE_TOOLS if topic.tools_enabled else [],
            )
            tool_ctx = ToolContext(
                turn_number=turn_number,
                max_turns=topic.max_turns,
                speaker=speaker,
                my_previous_claims=my_claims,
                opponent_previous_claims=opponent_claims,
                my_penalty_total=my_accumulated_penalty,
            )
            start_time = time.monotonic()
            ws_response = await asyncio.wait_for(
                ws_manager.request_turn(
                    match.id, agent.id, ws_request,
                    tool_executor=DebateToolExecutor(),
                    tool_context=tool_ctx,
                ),
                timeout=settings.debate_turn_timeout_seconds,
            )
            elapsed = time.monotonic() - start_time
            response_time_ms = int(elapsed * 1000)

            action = ws_response.action
            claim = ws_response.claim
            evidence = ws_response.evidence
            raw_response = {
                "action": ws_response.action,
                "claim": ws_response.claim,
                "evidence": ws_response.evidence,
                "tool_used": ws_response.tool_used,
                "tool_result": ws_response.tool_result,
            }

            # local 에이전트도 프론트 타이핑 애니메이션 활성화 — claim 전체를 단일 chunk로 발행
            await publish_event(str(match.id), "turn_chunk", {
                "turn_number": turn_number,
                "speaker": speaker,
                "chunk": json.dumps({"action": action, "claim": claim}, ensure_ascii=False),
            })

        else:
            # 스트리밍 BYOK — 토큰별로 turn_chunk 이벤트 발행
            messages = _build_messages(
                system_prompt, topic, turn_number, speaker, my_claims, opponent_claims
            )
            start_time = time.monotonic()
            usage_out: dict = {}
            full_text = ""

            async with asyncio.timeout(settings.debate_turn_timeout_seconds):
                async for chunk in client.generate_stream_byok(
                    provider=agent.provider,
                    model_id=agent.model_id,
                    api_key=api_key,
                    messages=messages,
                    usage_out=usage_out,
                    max_tokens=topic.turn_token_limit,
                    temperature=0.7,
                ):
                    full_text += chunk
                    await publish_event(str(match.id), "turn_chunk", {
                        "turn_number": turn_number,
                        "speaker": speaker,
                        "chunk": chunk,
                    })

            elapsed = time.monotonic() - start_time
            response_time_ms = int(elapsed * 1000)

            response_text = full_text
            parsed = validate_response_schema(response_text)
            input_tokens = usage_out.get("input_tokens", 0)
            output_tokens = usage_out.get("output_tokens", 0)

            if usage_out.get("finish_reason") == "length":
                # 토픽 turn_token_limit 초과로 응답이 절삭됨 — 파싱 가능하면 그대로 사용, 불가하면 원문 절삭
                if parsed is None:
                    claim = response_text[:500]
                    raw_response = {"raw": response_text}
                else:
                    action = parsed["action"]
                    claim = parsed["claim"]
                    evidence = parsed.get("evidence")
                    raw_response = {
                        "action": parsed["action"],
                        "claim": parsed["claim"],
                        "evidence": parsed.get("evidence"),
                        "tool_used": parsed.get("tool_used"),
                        "tool_result": parsed.get("tool_result"),
                    }
            elif parsed is None:
                # JSON 파싱 불가 또는 스키마 불일치 — 원문을 발언으로 사용
                claim = response_text[:500]
                raw_response = {"raw": response_text}
            else:
                action = parsed["action"]
                claim = parsed["claim"]
                evidence = parsed.get("evidence")
                raw_response = {
                    "action": parsed["action"],
                    "claim": parsed["claim"],
                    "evidence": parsed.get("evidence"),
                    "tool_used": parsed.get("tool_used"),
                    "tool_result": parsed.get("tool_result"),
                }

        # 동어반복 감지
        if detect_repetition(claim, my_claims):
            penalties["repetition"] = PENALTY_REPETITION
            penalty_total += PENALTY_REPETITION

    except Exception:
        # TimeoutError 포함 모든 예외를 그대로 전파 — _execute_turn_with_retry가 재시도·부전패 처리
        raise

    # BYOK 에이전트 턴 토큰 사용량 기록 (테스트 매치 포함)
    if agent.provider != "local":
        await _log_orchestrator_usage(db, agent.owner_id, agent.model_id, input_tokens, output_tokens)

    turn = DebateTurnLog(
        match_id=match.id,
        turn_number=turn_number,
        speaker=speaker,
        agent_id=agent.id,
        action=action,
        claim=claim,
        evidence=evidence,
        raw_response=raw_response,
        penalties=penalties if penalties else None,
        penalty_total=penalty_total,
        response_time_ms=response_time_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(turn)
    await db.flush()
    return turn


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
    """재시도 포함 턴 실행. 모든 재시도 실패 시 None 반환."""
    for attempt in range(settings.debate_turn_max_retries + 1):
        try:
            return await _execute_turn(
                db, client, match, topic, turn_number, speaker,
                agent, version, api_key, my_claims, opponent_claims,
                my_accumulated_penalty=my_accumulated_penalty,
            )
        except Exception as exc:
            if attempt < settings.debate_turn_max_retries:
                logger.warning(
                    "Turn %d %s failed (attempt %d/%d): %s — retrying",
                    turn_number, speaker, attempt + 1, settings.debate_turn_max_retries + 1, exc,
                )
            else:
                logger.error(
                    "Turn %d %s failed after %d attempts: %s — forfeit",
                    turn_number, speaker, settings.debate_turn_max_retries + 1, exc,
                )
                return None
    return None


def _build_messages(
    system_prompt: str,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    my_claims: list[str],
    opponent_claims: list[str],
) -> list[dict]:
    """에이전트에게 보낼 메시지 컨텍스트 구성."""
    side_label = "A (찬성)" if speaker == "agent_a" else "B (반대)"
    tools_line = (
        "툴 사용: 허용됨 (calculator, stance_tracker, opponent_summary, turn_info)"
        if topic.tools_enabled
        else "툴 사용: 이 토론에서는 툴 사용이 금지되어 있습니다. tool_used는 반드시 null로 설정하세요."
    )
    context = f"""토론 포지션: {side_label}

토론 주제: {topic.title}
설명: {topic.description or '없음'}
현재 턴: {turn_number} / {topic.max_turns}
{tools_line}

⚠️ claim 필드에도 에이전트 시스템 프롬프트에서 지정한 어투·말투·캐릭터를 반드시 유지하세요.

{RESPONSE_SCHEMA_INSTRUCTION}"""

    # 시스템 프롬프트를 뒤에 배치해 어투/캐릭터 설정이 context보다 우선 적용되도록 함
    messages = [{"role": "system", "content": context + "\n\n---\n\n" + system_prompt}]

    # 이전 턴 히스토리 (최근 4턴)
    all_turns = []
    for _i, (my_c, opp_c) in enumerate(zip(my_claims, opponent_claims, strict=False)):
        all_turns.append({"role": "assistant", "content": my_c})
        all_turns.append({"role": "user", "content": f"[상대방]: {opp_c}"})

    # 상대방이 더 많이 말한 경우
    if len(opponent_claims) > len(my_claims):
        for opp_c in opponent_claims[len(my_claims):]:
            all_turns.append({"role": "user", "content": f"[상대방]: {opp_c}"})

    # 최근 4개만 유지
    messages.extend(all_turns[-4:])

    # 턴 단계별 전략 힌트: 초반·중반·후반에 따라 다른 액션을 유도한다
    is_final_turn = turn_number == topic.max_turns
    is_penultimate = topic.max_turns > 2 and turn_number == topic.max_turns - 1
    is_early = turn_number <= 2

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "먼저 시작하세요. 주제에 대한 첫 번째 주장을 한국어로 제시하세요."})
    elif opponent_claims:
        last_opp = opponent_claims[-1]

        if is_final_turn:
            strategy_hint = (
                "이번이 마지막 발언입니다. 지금까지의 논점을 간결하게 압축하고 핵심 입장을 마무리하세요. "
                "summarize 액션을 적극 활용하세요."
            )
        elif is_penultimate:
            strategy_hint = (
                "클라이맥스 국면입니다. 상대 논거의 핵심 약점에 집중하거나(rebut/question), "
                "인정할 부분은 인정하되 핵심 입장을 굳건히 하세요(concede)."
            )
        elif is_early:
            strategy_hint = (
                "초반 국면입니다. 새로운 논거를 제시(argue)하거나 상대의 전제에 의문을 제기(question)하세요."
            )
        else:
            strategy_hint = (
                "반박(rebut)·새 주장(argue)·질문(question)·인정 후 입장 유지(concede) 중 "
                "지금 상황에서 가장 설득력 있는 전략을 선택하세요."
            )

        base_content = (
            f"[직전 발언]\n{last_opp}\n\n"
            "위 발언을 바탕으로 토론을 이어가세요. "
            "'상대방은'으로 문장을 시작하지 마세요 — 논점이나 근거로 바로 시작하세요. "
            f"{strategy_hint}"
        )
        # Agent B의 첫 발언: 주도적으로 논점을 선점하도록 격려 (A측 편향 보정)
        if speaker == "agent_b" and not my_claims:
            base_content += (
                "\n\n(참고: 상대가 먼저 발언했지만, 당신도 새로운 논거로 주도적으로 쟁점을 선점할 수 있습니다.)"
            )
        messages.append({"role": "user", "content": base_content})
    else:
        messages.append({"role": "user", "content": "당신의 차례입니다. 주제에 대한 다음 주장을 한국어로 제시하세요."})

    return messages


async def _load_turns(db: AsyncSession, match_id) -> list[DebateTurnLog]:
    result = await db.execute(
        select(DebateTurnLog)
        .where(DebateTurnLog.match_id == match_id)
        .order_by(DebateTurnLog.turn_number, DebateTurnLog.speaker)
    )
    return list(result.scalars().all())


async def _execute_multi_and_finalize(
    match: DebateMatch,
    topic,
    db: AsyncSession,
    client,
    orchestrator,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
) -> None:
    """2v2/3v3 라운드 로빈: A팀과 B팀의 각 슬롯별로 기존 _execute_turn() 재사용.

    1v1 로직을 깨뜨리지 않도록 별도 함수로 분리.
    판정/ELO 갱신/이벤트 발행까지 처리.
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
        return

    max_slots = max(len(team_a), len(team_b))

    # 루프 진입 전 필요한 에이전트/버전을 한 번에 배치 조회하여 캐싱 (중복 쿼리 방지)
    all_agent_ids = list({p.agent_id for p in parts if p.agent_id is not None})
    agents_res = await db.execute(
        select(DebateAgent).where(DebateAgent.id.in_(all_agent_ids))
    )
    agents_cache: dict = {str(a.id): a for a in agents_res.scalars().all()}

    all_version_ids = list({p.version_id for p in parts if p.version_id is not None})
    versions_cache: dict = {}
    if all_version_ids:
        versions_res = await db.execute(
            select(DebateAgentVersion).where(DebateAgentVersion.id.in_(all_version_ids))
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

            turn_a = await _execute_turn(
                db, client, match, topic, turn_num, "agent_a",
                multi_agent_a, ver_a, key_a, claims_a, claims_b,
                my_accumulated_penalty=total_penalty_a,
            )
            total_penalty_a += turn_a.penalty_total
            claims_a.append(turn_a.claim)

            await publish_event(str(match.id), "turn", {
                "turn_number": turn_num,
                "speaker": f"agent_a_slot{i}",
                "action": turn_a.action,
                "claim": turn_a.claim,
                "evidence": turn_a.evidence,
                "penalties": turn_a.penalties,
                "penalty_total": turn_a.penalty_total,
            })

            turn_b = await _execute_turn(
                db, client, match, topic, turn_num, "agent_b",
                multi_agent_b, ver_b, key_b, claims_b, claims_a,
                my_accumulated_penalty=total_penalty_b,
            )
            total_penalty_b += turn_b.penalty_total
            claims_b.append(turn_b.claim)

            await publish_event(str(match.id), "turn", {
                "turn_number": turn_num,
                "speaker": f"agent_b_slot{i}",
                "action": turn_b.action,
                "claim": turn_b.claim,
                "evidence": turn_b.evidence,
                "penalties": turn_b.penalties,
                "penalty_total": turn_b.penalty_total,
            })

    match.penalty_a = total_penalty_a
    match.penalty_b = total_penalty_b
    await db.commit()
    logger.info("Multi-agent match %s turns completed", match.id)

    # 판정
    turns = await _load_turns(db, match.id)
    judgment = await orchestrator.judge(
        match, turns, topic, agent_a_name=agent_a.name, agent_b_name=agent_b.name
    )

    await _log_orchestrator_usage(
        db, agent_a.owner_id, judgment.get("model_id", ""),
        judgment["input_tokens"], judgment["output_tokens"],
    )

    if judgment["winner_id"] == match.agent_a_id:
        elo_result = "a_win"
    elif judgment["winner_id"] == match.agent_b_id:
        elo_result = "b_win"
    else:
        elo_result = "draw"

    score_diff = abs(judgment["score_a"] - judgment["score_b"])
    elo_a_before = agent_a.elo_rating
    elo_b_before = agent_b.elo_rating
    new_a, new_b = calculate_elo(elo_a_before, elo_b_before, elo_result, score_diff=score_diff)

    match.scorecard = judgment["scorecard"]
    match.score_a = judgment["score_a"]
    match.score_b = judgment["score_b"]
    match.winner_id = judgment["winner_id"]
    match.status = "completed"
    match.finished_at = datetime.now(UTC)

    agent_service = DebateAgentService(db)
    result_a = "win" if elo_result == "a_win" else ("loss" if elo_result == "b_win" else "draw")
    result_b = "win" if elo_result == "b_win" else ("loss" if elo_result == "a_win" else "draw")
    # 테스트 매치는 ELO·전적 미반영
    if not match.is_test:
        await agent_service.update_elo(str(agent_a.id), new_a, result_a)
        await agent_service.update_elo(str(agent_b.id), new_b, result_b)
        # 시즌 매치이면 시즌 ELO/전적 별도 갱신
        if match.season_id:
            from app.services.debate.season_service import DebateSeasonService
            season_svc = DebateSeasonService(db)
            stats_a = await season_svc.get_or_create_season_stats(str(agent_a.id), str(match.season_id))
            stats_b = await season_svc.get_or_create_season_stats(str(agent_b.id), str(match.season_id))
            season_new_a, season_new_b = calculate_elo(
                stats_a.elo_rating, stats_b.elo_rating, elo_result, score_diff=score_diff
            )
            await season_svc.update_season_stats(str(agent_a.id), str(match.season_id), season_new_a, result_a)
            await season_svc.update_season_stats(str(agent_b.id), str(match.season_id), season_new_b, result_b)

    await db.execute(
        update(DebateMatch)
        .where(DebateMatch.id == match.id)
        .values(elo_a_before=elo_a_before, elo_b_before=elo_b_before, elo_a_after=new_a, elo_b_after=new_b)
    )
    await db.commit()

    # 예측 정산 + 토너먼트 + 요약
    from app.services.debate.match_service import DebateMatchService
    match_service = DebateMatchService(db)
    await match_service.resolve_predictions(
        str(match.id),
        str(match.winner_id) if match.winner_id else None,
        str(match.agent_a_id),
        str(match.agent_b_id),
    )
    if match.tournament_id:
        from app.services.debate.tournament_service import DebateTournamentService
        await DebateTournamentService(db).advance_round(str(match.tournament_id))
    if settings.debate_summary_enabled:
        from app.services.debate.match_service import generate_summary_task
        asyncio.create_task(generate_summary_task(str(match.id)))

    await publish_event(str(match.id), "finished", {
        "winner_id": str(judgment["winner_id"]) if judgment["winner_id"] else None,
        "score_a": judgment["score_a"],
        "score_b": judgment["score_b"],
        "elo_a": new_a,
        "elo_b": new_b,
    })
