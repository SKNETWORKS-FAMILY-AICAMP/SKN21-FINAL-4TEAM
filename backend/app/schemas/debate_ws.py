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


class WSTurnResponse(BaseModel):
    """에이전트 → 서버: 턴 응답."""

    type: Literal["turn_response"] = "turn_response"
    match_id: UUID
    action: str
    claim: str
    evidence: str | None = None
    tool_used: str | None = None
    tool_result: str | None = None


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
