"""단일 턴 실행 로직. _execute_turn / _execute_turn_with_retry를 클래스로 캡슐화."""

import asyncio
import json
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.schemas.debate_ws import WSTurnRequest
from app.services.debate.broadcast import publish_event
from app.services.debate.helpers import (
    _build_messages,
    validate_response_schema,
)
from app.services.debate.tool_executor import AVAILABLE_TOOLS, DebateToolExecutor, ToolContext
from app.services.debate.ws_manager import WSConnectionManager
from app.services.llm.inference_client import InferenceClient
from app.services.debate.exceptions import MatchVoidError
from app.services.llm.providers.base import APIKeyError

logger = logging.getLogger(__name__)


class TurnExecutor:
    """단일 턴 실행(LLM 스트리밍 or WebSocket) 및 재시도 로직을 담당하는 클래스."""

    def __init__(self, client: InferenceClient, db: AsyncSession) -> None:
        self.client = client
        self.db = db

    async def execute(
        self,
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
        event_meta: dict | None = None,
    ) -> DebateTurnLog:
        """단일 턴을 실행하고 DB에 기록한다.

        로컬 에이전트는 WebSocket 경유, 외부 에이전트는 스트리밍 BYOK 방식으로 처리.
        실패 시 예외를 그대로 전파 — execute_with_retry()가 재시도를 담당한다.

        Args:
            match: 진행 중인 매치.
            topic: 토론 주제.
            turn_number: 현재 턴 번호.
            speaker: 발언자 ('agent_a' | 'agent_b').
            agent: 발언 에이전트.
            version: 에이전트 버전 스냅샷. 없으면 기본 프롬프트 사용.
            api_key: LLM BYOK 또는 플랫폼 API 키.
            my_claims: 본인의 이전 발언 목록.
            opponent_claims: 상대방의 이전 발언 목록.
            my_accumulated_penalty: 이번 턴 이전까지 누적 벌점.

        Returns:
            DB에 저장된 DebateTurnLog 객체.

        Raises:
            TimeoutError: 턴 타임아웃 초과.
            APIKeyError: API 키 인증 실패.
            Exception: 기타 LLM/WebSocket 오류.
        """
        from app.services.debate.debate_formats import _log_orchestrator_usage

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
                chunk_payload = {
                    "turn_number": turn_number,
                    "speaker": speaker,
                    "chunk": json.dumps({"action": action, "claim": claim}, ensure_ascii=False),
                }
                if event_meta:
                    chunk_payload.update(event_meta)
                await publish_event(str(match.id), "turn_chunk", chunk_payload)

            else:
                # 스트리밍 BYOK — 토큰별로 turn_chunk 이벤트 발행
                messages = _build_messages(
                    system_prompt, topic, turn_number, speaker, my_claims, opponent_claims
                )
                start_time = time.monotonic()
                usage_out: dict = {}
                full_text = ""

                async with asyncio.timeout(settings.debate_turn_timeout_seconds):
                    async for chunk in self.client.generate_stream_byok(
                        provider=agent.provider,
                        model_id=agent.model_id,
                        api_key=api_key,
                        messages=messages,
                        usage_out=usage_out,
                        max_tokens=topic.turn_token_limit,
                        temperature=0.7,
                    ):
                        full_text += chunk
                        chunk_payload = {
                            "turn_number": turn_number,
                            "speaker": speaker,
                            "chunk": chunk,
                        }
                        if event_meta:
                            chunk_payload.update(event_meta)
                        await publish_event(str(match.id), "turn_chunk", chunk_payload)

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

        except Exception:
            # TimeoutError 포함 모든 예외를 그대로 전파 — execute_with_retry가 재시도·부전패 처리
            raise

        # BYOK 에이전트 턴 토큰 사용량 기록 (테스트 매치 포함)
        if agent.provider != "local":
            await _log_orchestrator_usage(self.db, agent.owner_id, agent.model_id, input_tokens, output_tokens)

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
        self.db.add(turn)
        await self.db.flush()
        return turn

    async def execute_with_retry(
        self,
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
        event_meta: dict | None = None,
    ) -> DebateTurnLog | None:
        """재시도 로직을 포함한 턴 실행. 모든 재시도 실패 시 None을 반환한다.

        APIKeyError는 1회만 재시도 후 MatchVoidError로 변환.
        그 외 예외는 debate_turn_max_retries 횟수까지 재시도 후 None 반환.

        Args:
            match: 진행 중인 매치.
            topic: 토론 주제.
            turn_number: 현재 턴 번호.
            speaker: 발언자 ('agent_a' | 'agent_b').
            agent: 발언 에이전트.
            version: 에이전트 버전 스냅샷.
            api_key: LLM API 키.
            my_claims: 본인의 이전 발언 목록.
            opponent_claims: 상대방의 이전 발언 목록.
            my_accumulated_penalty: 누적 벌점.

        Returns:
            성공 시 DebateTurnLog, 모든 재시도 실패 시 None.

        Raises:
            MatchVoidError: APIKeyError가 2회 연속 발생한 경우 (기술적 장애).
        """
        for attempt in range(settings.debate_turn_max_retries + 1):
            try:
                return await self.execute(
                    match, topic, turn_number, speaker,
                    agent, version, api_key, my_claims, opponent_claims,
                    my_accumulated_penalty=my_accumulated_penalty,
                    event_meta=event_meta,
                )
            except APIKeyError as exc:
                if attempt == 0:
                    # 일시적 인증 오류 가능성 — 1회 재시도
                    logger.warning("Turn %d %s API key error (attempt 1) — retrying once: %s", turn_number, speaker, exc)
                    await asyncio.sleep(1.0)
                    continue
                # 2회 연속 실패 → 기술적 장애로 매치 무효화
                raise MatchVoidError(
                    f"API key authentication failed after retry for agent {getattr(agent, 'id', 'unknown')}: {exc}"
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
