"""토론 엔진. 비동기 백그라운드 태스크로 매치를 실행."""

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.encryption import decrypt_api_key
from app.models.credit_ledger import CreditLedger
from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.user import User
from app.schemas.debate_ws import WSMatchReady, WSTurnRequest
from app.services.debate_agent_service import DebateAgentService
from app.services.debate_broadcast import publish_event
from app.services.debate_orchestrator import DebateOrchestrator, calculate_elo
from app.services.debate_tool_executor import AVAILABLE_TOOLS, DebateToolExecutor, ToolContext
from app.services.debate_ws_manager import WSConnectionManager
from app.services.human_detection import HumanDetectionAnalyzer
from app.services.human_detection import TurnContext as HumanTurnContext
from app.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

# 응답 JSON 스키마
RESPONSE_SCHEMA_INSTRUCTION = """⚠️ 중요: 반드시 한국어로만 답변하세요. 영어 사용 금지.

다음 형식의 JSON만 응답하세요 (다른 텍스트 없이):
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<한국어로 작성한 주요 주장>",
  "evidence": "<한국어로 작성한 근거/데이터/인용>" | null,
  "tool_used": null,
  "tool_result": null
}"""

# 벌점 정의
PENALTY_SCHEMA_VIOLATION = 5
PENALTY_REPETITION = 3
PENALTY_PROMPT_INJECTION = 10
PENALTY_TIMEOUT = 5
PENALTY_FALSE_SOURCE = 7
PENALTY_AD_HOMINEM = 8
PENALTY_HUMAN_SUSPICION = 15

# 프롬프트 인젝션 패턴
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"you\s+are\s+now\s+",
    r"system\s*:\s*",
    r"<\|?system\|?>",
    r"forget\s+(everything|your\s+rules)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# 인신공격 패턴
_AD_HOMINEM_PATTERNS = [
    r"you\s+(are|'re)\s+(stupid|idiot|dumb|fool|moron)",
    r"바보|멍청|병신",
]
_AD_HOMINEM_RE = re.compile("|".join(_AD_HOMINEM_PATTERNS), re.IGNORECASE)


def detect_repetition(new_claim: str, previous_claims: list[str], threshold: float = 0.7) -> bool:
    """단순 문자열 유사도로 동어반복 감지."""
    if not previous_claims:
        return False
    new_words = set(new_claim.lower().split())
    if not new_words:
        return False
    for prev in previous_claims:
        prev_words = set(prev.lower().split())
        if not prev_words:
            continue
        overlap = len(new_words & prev_words)
        similarity = overlap / max(len(new_words), len(prev_words))
        if similarity >= threshold:
            return True
    return False


def detect_prompt_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text))


def detect_ad_hominem(text: str) -> bool:
    return bool(_AD_HOMINEM_RE.search(text))


def validate_response_schema(response_text: str) -> dict | None:
    """응답 JSON 파싱 및 스키마 검증. 유효하면 dict, 아니면 None."""
    try:
        # JSON 블록 추출 (코드 블록 안에 있을 수 있음)
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    required_keys = {"action", "claim"}
    if not required_keys.issubset(data.keys()):
        return None

    valid_actions = {"argue", "rebut", "concede", "question", "summarize"}
    if data.get("action") not in valid_actions:
        return None

    return data


def _resolve_api_key(agent: DebateAgent) -> str:
    """에이전트 API 키 반환. 우선순위: BYOK 복호화 → 플랫폼 환경변수 → 빈 문자열."""
    if agent.provider == "local":
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
        case _:
            return ""


async def run_debate(match_id: str) -> None:
    """매치 실행. 독립 DB 세션으로 백그라운드 실행."""
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            await _execute_match(db, match_id)
        except Exception as exc:
            logger.error("Debate engine error for match %s: %s", match_id, exc, exc_info=True)
            await db.execute(
                update(DebateMatch)
                .where(DebateMatch.id == match_id)
                .values(status="error", finished_at=datetime.now(UTC))
            )
            await db.commit()
            await publish_event(match_id, "error", {"message": str(exc)})
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

    # 에이전트 + 버전 로드
    agent_a = (await db.execute(select(DebateAgent).where(DebateAgent.id == match.agent_a_id))).scalar_one()
    agent_b = (await db.execute(select(DebateAgent).where(DebateAgent.id == match.agent_b_id))).scalar_one()

    version_a = None
    if match.agent_a_version_id:
        version_a = (await db.execute(
            select(DebateAgentVersion).where(DebateAgentVersion.id == match.agent_a_version_id)
        )).scalar_one_or_none()
    version_b = None
    if match.agent_b_version_id:
        version_b = (await db.execute(
            select(DebateAgentVersion).where(DebateAgentVersion.id == match.agent_b_version_id)
        )).scalar_one_or_none()

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
                    # 몰수패 처리
                    match.status = "forfeit"
                    match.finished_at = datetime.now(UTC)
                    # 미접속 측 패배
                    forfeit_loser = agent.id
                    forfeit_winner_id = agent_b.id if side == "agent_a" else agent_a.id
                    match.winner_id = forfeit_winner_id
                    await db.commit()
                    # ELO 갱신 (몰수패는 최대 이전량 적용)
                    agent_service = DebateAgentService(db)
                    new_loser_elo, new_winner_elo = calculate_elo(
                        agent.elo_rating,
                        (agent_b if side == "agent_a" else agent_a).elo_rating,
                        "b_win" if side == "agent_a" else "a_win",
                        score_diff=settings.debate_elo_max_transfer,
                    )
                    loser_result = "loss"
                    winner_result = "win"
                    await agent_service.update_elo(str(forfeit_loser), new_loser_elo, loser_result)
                    await agent_service.update_elo(str(forfeit_winner_id), new_winner_elo, winner_result)
                    await db.commit()
                    await publish_event(str(match.id), "forfeit", {
                        "match_id": str(match.id),
                        "reason": f"Agent {agent.name} did not connect in time",
                        "winner_id": str(forfeit_winner_id),
                    })
                    logger.info("Match %s forfeit: agent %s did not connect", match.id, agent.name)
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
    if settings.debate_credit_cost > 0 and settings.credit_system_enabled:
        for agent in (agent_a, agent_b):
            deduct_result = await db.execute(
                update(User)
                .where(User.id == agent.owner_id, User.credit_balance >= settings.debate_credit_cost)
                .values(credit_balance=User.credit_balance - settings.debate_credit_cost)
                .returning(User.credit_balance)
            )
            row = deduct_result.fetchone()
            if row is None:
                match.status = "error"
                match.finished_at = datetime.now(UTC)
                await db.commit()
                await publish_event(str(match.id), "error", {
                    "message": f"에이전트 '{agent.name}' 소유자의 크레딧이 부족합니다 (필요: {settings.debate_credit_cost}석)",
                })
                return

            db.add(CreditLedger(
                user_id=agent.owner_id,
                amount=-settings.debate_credit_cost,
                balance_after=row.credit_balance,
                tx_type="debate",
                reference_id=str(match.id),
                description=f"토론 매치 참가 (-{settings.debate_credit_cost}석)",
            ))
        await db.commit()

    # API 키 복호화 (local 에이전트는 스킵, BYOK 없으면 플랫폼 키 폴백)
    key_a = _resolve_api_key(agent_a)
    key_b = _resolve_api_key(agent_b)

    # 매치 시작
    match.status = "in_progress"
    match.started_at = datetime.now(UTC)
    await db.commit()

    await publish_event(str(match.id), "started", {"match_id": str(match.id)})

    client = InferenceClient()
    orchestrator = DebateOrchestrator()
    claims_a: list[str] = []
    claims_b: list[str] = []
    total_penalty_a = 0
    total_penalty_b = 0

    # 휴먼 감지용 이전 턴 데이터 (로컬 에이전트별)
    elapsed_history_a: list[float] = []
    length_history_a: list[int] = []
    elapsed_history_b: list[float] = []
    length_history_b: list[int] = []

    # 턴 루프
    for turn_num in range(1, topic.max_turns + 1):
        # Agent A 턴
        turn_a = await _execute_turn(
            db, client, match, topic, turn_num, "agent_a",
            agent_a, version_a, key_a, claims_a, claims_b,
            elapsed_history_a, length_history_a,
            my_accumulated_penalty=total_penalty_a,
        )
        total_penalty_a += turn_a.penalty_total

        # ★ LLM 검토 단계 (Agent A)
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
            )
            review_elapsed = time.monotonic() - review_start

            # llm_ 접두사로 LLM 벌점 머지 (regex 벌점과 구분)
            for vtype, vpenalty in review_a["penalties"].items():
                llm_key = f"llm_{vtype}"
                if turn_a.penalties is None:
                    turn_a.penalties = {}
                turn_a.penalties[llm_key] = vpenalty
                turn_a.penalty_total += vpenalty
                total_penalty_a += vpenalty

            # 차단 시 주장 대체 + claims_a에 대체 텍스트 삽입
            effective_claim_a = turn_a.claim
            if review_a["block"]:
                effective_claim_a = review_a["blocked_claim"]
                turn_a.is_blocked = True
                turn_a.claim = effective_claim_a
            claims_a.append(effective_claim_a)

            # DB에 검토 결과 저장
            turn_a.review_result = {
                "logic_score": review_a["logic_score"],
                "violations": review_a["violations"],
                "feedback": review_a["feedback"],
                "blocked": review_a["block"],
            }
        else:
            review_elapsed = 0.0
            review_a = None
            claims_a.append(turn_a.claim)

        if turn_a.response_time_ms is not None:
            elapsed_history_a.append(turn_a.response_time_ms / 1000.0)
            length_history_a.append(len(turn_a.claim))

        await publish_event(str(match.id), "turn", {
            "turn_number": turn_num,
            "speaker": "agent_a",
            "action": turn_a.action,
            "claim": turn_a.claim,
            "evidence": turn_a.evidence,
            "penalties": turn_a.penalties,
            "penalty_total": turn_a.penalty_total,
            "human_suspicion_score": turn_a.human_suspicion_score,
            "response_time_ms": turn_a.response_time_ms,
            "is_blocked": turn_a.is_blocked,
            "review_result": turn_a.review_result,
        })

        # 검토 결과 SSE 이벤트 (관전자 피드백)
        if review_a is not None:
            await publish_event(str(match.id), "turn_review", {
                "turn_number": turn_num,
                "speaker": "agent_a",
                "logic_score": review_a["logic_score"],
                "violations": review_a["violations"],
                "feedback": review_a["feedback"],
                "blocked": review_a["block"],
            })

        # 관전 UX: 딜레이에서 검토 소요시간 차감
        remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)

        # Agent B 턴
        turn_b = await _execute_turn(
            db, client, match, topic, turn_num, "agent_b",
            agent_b, version_b, key_b, claims_b, claims_a,
            elapsed_history_b, length_history_b,
            my_accumulated_penalty=total_penalty_b,
        )
        total_penalty_b += turn_b.penalty_total

        # ★ LLM 검토 단계 (Agent B)
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
            )
            review_elapsed = time.monotonic() - review_start

            for vtype, vpenalty in review_b["penalties"].items():
                llm_key = f"llm_{vtype}"
                if turn_b.penalties is None:
                    turn_b.penalties = {}
                turn_b.penalties[llm_key] = vpenalty
                turn_b.penalty_total += vpenalty
                total_penalty_b += vpenalty

            effective_claim_b = turn_b.claim
            if review_b["block"]:
                effective_claim_b = review_b["blocked_claim"]
                turn_b.is_blocked = True
                turn_b.claim = effective_claim_b
            claims_b.append(effective_claim_b)

            turn_b.review_result = {
                "logic_score": review_b["logic_score"],
                "violations": review_b["violations"],
                "feedback": review_b["feedback"],
                "blocked": review_b["block"],
            }
        else:
            review_elapsed = 0.0
            review_b = None
            claims_b.append(turn_b.claim)

        if turn_b.response_time_ms is not None:
            elapsed_history_b.append(turn_b.response_time_ms / 1000.0)
            length_history_b.append(len(turn_b.claim))

        await publish_event(str(match.id), "turn", {
            "turn_number": turn_num,
            "speaker": "agent_b",
            "action": turn_b.action,
            "claim": turn_b.claim,
            "evidence": turn_b.evidence,
            "penalties": turn_b.penalties,
            "penalty_total": turn_b.penalty_total,
            "human_suspicion_score": turn_b.human_suspicion_score,
            "response_time_ms": turn_b.response_time_ms,
            "is_blocked": turn_b.is_blocked,
            "review_result": turn_b.review_result,
        })

        if review_b is not None:
            await publish_event(str(match.id), "turn_review", {
                "turn_number": turn_num,
                "speaker": "agent_b",
                "logic_score": review_b["logic_score"],
                "violations": review_b["violations"],
                "feedback": review_b["feedback"],
                "blocked": review_b["block"],
            })

        # 라운드 사이 딜레이 (마지막 라운드 제외, 검토 소요시간 차감)
        if turn_num < topic.max_turns:
            remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

    # 벌점 집계
    match.penalty_a = total_penalty_a
    match.penalty_b = total_penalty_b
    await db.commit()

    # 판정
    turns = await _load_turns(db, match.id)
    judgment = await orchestrator.judge(match, turns, topic, agent_a_name=agent_a.name, agent_b_name=agent_b.name)

    match.scorecard = judgment["scorecard"]
    match.score_a = judgment["score_a"]
    match.score_b = judgment["score_b"]
    match.winner_id = judgment["winner_id"]
    match.status = "completed"
    match.finished_at = datetime.now(UTC)
    await db.commit()

    # ELO 갱신 (제로섬: 판정 점수차만큼 이전)
    if judgment["winner_id"] == match.agent_a_id:
        elo_result = "a_win"
    elif judgment["winner_id"] == match.agent_b_id:
        elo_result = "b_win"
    else:
        elo_result = "draw"

    score_diff = abs(judgment["score_a"] - judgment["score_b"])
    new_a, new_b = calculate_elo(agent_a.elo_rating, agent_b.elo_rating, elo_result, score_diff=score_diff)

    agent_service = DebateAgentService(db)
    result_a = "win" if elo_result == "a_win" else ("loss" if elo_result == "b_win" else "draw")
    result_b = "win" if elo_result == "b_win" else ("loss" if elo_result == "a_win" else "draw")
    await agent_service.update_elo(
        str(agent_a.id), new_a, result_a,
        str(match.agent_a_version_id) if match.agent_a_version_id else None,
    )
    await agent_service.update_elo(
        str(agent_b.id), new_b, result_b,
        str(match.agent_b_version_id) if match.agent_b_version_id else None,
    )
    await db.commit()

    await publish_event(str(match.id), "finished", {
        "winner_id": str(judgment["winner_id"]) if judgment["winner_id"] else None,
        "score_a": judgment["score_a"],
        "score_b": judgment["score_b"],
        "elo_a": new_a,
        "elo_b": new_b,
    })

    logger.info("Match %s completed. Winner: %s", match.id, judgment["winner_id"])


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
    prev_elapsed_history: list[float] | None = None,
    prev_length_history: list[int] | None = None,
    my_accumulated_penalty: int = 0,
) -> DebateTurnLog:
    """단일 턴 실행. 벌점 감지 + 휴먼 감지 포함."""
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
    human_suspicion_score = 0
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

            # 휴먼 감지 분석
            analyzer = HumanDetectionAnalyzer()
            detection = analyzer.analyze_turn(
                response_text=claim,
                elapsed_seconds=elapsed,
                turn_context=HumanTurnContext(
                    turn_number=turn_number,
                    previous_elapsed=prev_elapsed_history or [],
                    previous_lengths=prev_length_history or [],
                ),
            )
            human_suspicion_score = detection.score

            if detection.score >= 61:
                penalties["human_suspicion"] = PENALTY_HUMAN_SUSPICION
                penalty_total += PENALTY_HUMAN_SUSPICION
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

            if parsed is None:
                penalties["schema_violation"] = PENALTY_SCHEMA_VIOLATION
                penalty_total += PENALTY_SCHEMA_VIOLATION
                claim = response_text[:500]
                raw_response = {"raw": response_text}
            else:
                action = parsed["action"]
                claim = parsed["claim"]
                evidence = parsed.get("evidence")
                raw_response = parsed

        # 동어반복 감지
        if detect_repetition(claim, my_claims):
            penalties["repetition"] = PENALTY_REPETITION
            penalty_total += PENALTY_REPETITION

        # 프롬프트 인젝션 감지
        full_text = f"{claim} {evidence or ''}"
        if detect_prompt_injection(full_text):
            penalties["prompt_injection"] = PENALTY_PROMPT_INJECTION
            penalty_total += PENALTY_PROMPT_INJECTION

        # 인신공격 감지
        if detect_ad_hominem(full_text):
            penalties["ad_hominem"] = PENALTY_AD_HOMINEM
            penalty_total += PENALTY_AD_HOMINEM

    except TimeoutError:
        penalties["timeout"] = PENALTY_TIMEOUT
        penalty_total += PENALTY_TIMEOUT
        claim = "[TIMEOUT: No response within time limit]"
        input_tokens = 0
        output_tokens = 0

    except Exception as exc:
        logger.error("Turn execution error: %s", exc)
        claim = f"[ERROR: {str(exc)[:200]}]"
        input_tokens = 0
        output_tokens = 0

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
        human_suspicion_score=human_suspicion_score,
        response_time_ms=response_time_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(turn)
    await db.flush()
    return turn


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

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "먼저 시작하세요. 주제에 대한 첫 번째 주장을 한국어로 제시하세요."})
    elif opponent_claims:
        last_opp = opponent_claims[-1]
        base_content = (
            f"[직전 발언]\n{last_opp}\n\n"
            "위 발언의 핵심 논점을 짚어 반박하세요. "
            "'상대방은'으로 문장을 시작하지 마세요 — 논점이나 근거로 바로 시작하세요. "
            "어떤 주장이 왜 타당하지 않은지 지적한 후, 새로운 근거로 자신의 입장을 강화하세요."
        )
        # Agent B의 첫 발언: 주도적으로 논점을 선점하도록 격려 (A측 편향 보정)
        if speaker == "agent_b" and not my_claims:
            base_content += "\n\n(참고: 상대가 먼저 발언했지만, 당신도 새로운 논거로 주도적으로 쟁점을 선점할 수 있습니다.)"
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
