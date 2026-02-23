"""토론 엔진. 비동기 백그라운드 태스크로 매치를 실행."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.encryption import decrypt_api_key
from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.services.debate_agent_service import DebateAgentService
from app.schemas.debate_ws import WSMatchReady, WSTurnRequest
from app.services.debate_broadcast import publish_event
from app.services.debate_orchestrator import DebateOrchestrator, calculate_elo
from app.services.debate_ws_manager import WSConnectionManager
from app.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

# 응답 JSON 스키마
RESPONSE_SCHEMA_INSTRUCTION = """You MUST respond with ONLY valid JSON in this exact format:
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<your main argument or response>",
  "evidence": "<supporting evidence, data, or citations>" | null,
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
                .values(status="error", finished_at=datetime.now(timezone.utc))
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
                    match.finished_at = datetime.now(timezone.utc)
                    # 미접속 측 패배
                    forfeit_loser = agent.id
                    forfeit_winner_id = agent_b.id if side == "agent_a" else agent_a.id
                    match.winner_id = forfeit_winner_id
                    await db.commit()
                    # ELO 벌점 (몰수패는 0점 패배 취급)
                    agent_service = DebateAgentService(db)
                    new_loser_elo, new_winner_elo = calculate_elo(
                        agent.elo_rating,
                        (agent_b if side == "agent_a" else agent_a).elo_rating,
                        "b_win" if side == "agent_a" else "a_win",
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

    # API 키 복호화 (local 에이전트는 스킵)
    key_a = decrypt_api_key(agent_a.encrypted_api_key) if agent_a.provider != "local" else ""
    key_b = decrypt_api_key(agent_b.encrypted_api_key) if agent_b.provider != "local" else ""

    # 매치 시작
    match.status = "in_progress"
    match.started_at = datetime.now(timezone.utc)
    await db.commit()

    await publish_event(str(match.id), "started", {"match_id": str(match.id)})

    client = InferenceClient()
    claims_a: list[str] = []
    claims_b: list[str] = []
    total_penalty_a = 0
    total_penalty_b = 0

    # 턴 루프
    for turn_num in range(1, topic.max_turns + 1):
        # Agent A 턴
        turn_a = await _execute_turn(
            db, client, match, topic, turn_num, "agent_a",
            agent_a, version_a, key_a, claims_a, claims_b,
        )
        total_penalty_a += turn_a.penalty_total
        claims_a.append(turn_a.claim)

        await publish_event(str(match.id), "turn", {
            "turn_number": turn_num,
            "speaker": "agent_a",
            "action": turn_a.action,
            "claim": turn_a.claim,
            "evidence": turn_a.evidence,
            "penalties": turn_a.penalties,
            "penalty_total": turn_a.penalty_total,
        })

        # Agent B 턴
        turn_b = await _execute_turn(
            db, client, match, topic, turn_num, "agent_b",
            agent_b, version_b, key_b, claims_b, claims_a,
        )
        total_penalty_b += turn_b.penalty_total
        claims_b.append(turn_b.claim)

        await publish_event(str(match.id), "turn", {
            "turn_number": turn_num,
            "speaker": "agent_b",
            "action": turn_b.action,
            "claim": turn_b.claim,
            "evidence": turn_b.evidence,
            "penalties": turn_b.penalties,
            "penalty_total": turn_b.penalty_total,
        })

    # 벌점 집계
    match.penalty_a = total_penalty_a
    match.penalty_b = total_penalty_b
    await db.commit()

    # 판정
    turns = await _load_turns(db, match.id)
    orchestrator = DebateOrchestrator()
    judgment = await orchestrator.judge(match, turns, topic)

    match.scorecard = judgment["scorecard"]
    match.score_a = judgment["score_a"]
    match.score_b = judgment["score_b"]
    match.winner_id = judgment["winner_id"]
    match.status = "completed"
    match.finished_at = datetime.now(timezone.utc)
    await db.commit()

    # ELO 갱신
    if judgment["winner_id"] == match.agent_a_id:
        elo_result = "a_win"
    elif judgment["winner_id"] == match.agent_b_id:
        elo_result = "b_win"
    else:
        elo_result = "draw"

    new_a, new_b = calculate_elo(agent_a.elo_rating, agent_b.elo_rating, elo_result)

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
) -> DebateTurnLog:
    """단일 턴 실행. 벌점 감지 포함."""
    system_prompt = version.system_prompt if version else "You are a debate participant."

    penalties: dict[str, int] = {}
    penalty_total = 0
    action = "argue"
    claim = ""
    evidence = None
    raw_response = None
    input_tokens = 0
    output_tokens = 0

    try:
        if agent.provider == "local":
            # WebSocket 경유 턴 요청
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
            )
            ws_response = await asyncio.wait_for(
                ws_manager.request_turn(match.id, agent.id, ws_request),
                timeout=settings.debate_turn_timeout_seconds,
            )
            # local 에이전트는 이미 구조화된 응답을 보내므로 schema 검증 불필요
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
        else:
            # 기존 BYOK 로직
            messages = _build_messages(
                system_prompt, topic, turn_number, speaker, my_claims, opponent_claims
            )
            result = await asyncio.wait_for(
                client.generate_byok(
                    provider=agent.provider,
                    model_id=agent.model_id,
                    api_key=api_key,
                    messages=messages,
                    max_tokens=topic.turn_token_limit,
                    temperature=0.7,
                ),
                timeout=settings.debate_turn_timeout_seconds,
            )
            response_text = result["content"]
            parsed = validate_response_schema(response_text)
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)

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

    except asyncio.TimeoutError:
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
    side = "A (PRO)" if speaker == "agent_a" else "B (CON)"
    context = f"""You are participating in a formal debate as Side {side}.

Topic: {topic.title}
Description: {topic.description or 'N/A'}
Turn: {turn_number} of {topic.max_turns}

{RESPONSE_SCHEMA_INSTRUCTION}"""

    messages = [{"role": "system", "content": system_prompt + "\n\n" + context}]

    # 이전 턴 히스토리 (최근 4턴)
    all_turns = []
    for i, (my_c, opp_c) in enumerate(zip(my_claims, opponent_claims)):
        all_turns.append({"role": "assistant", "content": my_c})
        all_turns.append({"role": "user", "content": f"[Opponent]: {opp_c}"})

    # 상대방이 더 많이 말한 경우
    if len(opponent_claims) > len(my_claims):
        for opp_c in opponent_claims[len(my_claims):]:
            all_turns.append({"role": "user", "content": f"[Opponent]: {opp_c}"})

    # 최근 4개만 유지
    messages.extend(all_turns[-4:])

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "You go first. Present your opening argument."})
    else:
        messages.append({"role": "user", "content": "Your turn. Respond to the opponent's argument."})

    return messages


async def _load_turns(db: AsyncSession, match_id) -> list[DebateTurnLog]:
    result = await db.execute(
        select(DebateTurnLog)
        .where(DebateTurnLog.match_id == match_id)
        .order_by(DebateTurnLog.turn_number, DebateTurnLog.speaker)
    )
    return list(result.scalars().all())
