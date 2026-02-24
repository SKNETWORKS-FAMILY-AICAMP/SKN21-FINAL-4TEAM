"""WebSocket 프로토콜 메시지 스키마. 로컬 에이전트와 서버 간 통신 형식 정의."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class WSTurnRequest(BaseModel):
    """서버 → 에이전트: 턴 요청."""

    type: Literal["turn_request"] = "turn_request"
    match_id: UUID
    turn_number: int
    speaker: str
    topic_title: str
    topic_description: str | None
    max_turns: int
    turn_token_limit: int
    my_previous_claims: list[str]
    opponent_previous_claims: list[str]
    time_limit_seconds: int
    available_tools: list[str] = []  # 서버가 지원하는 툴 목록


class WSTurnResponse(BaseModel):
    """에이전트 → 서버: 턴 최종 응답."""

    type: Literal["turn_response"] = "turn_response"
    match_id: UUID
    action: str
    claim: str
    evidence: str | None = None
    tool_used: str | None = None
    tool_result: str | None = None


class WSToolRequest(BaseModel):
    """에이전트 → 서버: 툴 실행 요청.

    에이전트가 최종 응답(turn_response)을 보내기 전에
    서버 측 툴을 호출할 때 사용한다.
    """

    type: Literal["tool_request"] = "tool_request"
    match_id: UUID
    turn_number: int
    tool_name: str  # "calculator" | "stance_tracker" | "opponent_summary" | "turn_info"
    tool_input: str = ""  # calculator용 수식, 나머지 툴은 빈 문자열


class WSToolResult(BaseModel):
    """서버 → 에이전트: 툴 실행 결과."""

    type: Literal["tool_result"] = "tool_result"
    tool_name: str
    result: str
    error: str | None = None


class WSMatchReady(BaseModel):
    """서버 → 에이전트: 매치 시작 알림."""

    type: Literal["match_ready"] = "match_ready"
    match_id: UUID
    topic_title: str
    opponent_name: str
    your_side: str


class WSError(BaseModel):
    """서버 → 에이전트: 에러."""

    type: Literal["error"] = "error"
    message: str
    code: str | None = None


class WSHeartbeat(BaseModel):
    type: Literal["ping", "pong"]
