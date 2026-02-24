from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JoinQueueRequest(BaseModel):
    agent_id: UUID = Field(...)


class AgentSummary(BaseModel):
    id: UUID
    name: str
    provider: str
    model_id: str
    elo_rating: int

    model_config = {"from_attributes": True}


class TurnLogResponse(BaseModel):
    id: UUID
    turn_number: int
    speaker: str
    agent_id: UUID
    action: str
    claim: str
    evidence: str | None
    tool_used: str | None
    tool_result: str | None
    penalties: dict | None
    penalty_total: int
    human_suspicion_score: int = 0
    response_time_ms: int | None = None
    input_tokens: int
    output_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ScorecardResponse(BaseModel):
    agent_a: dict
    agent_b: dict
    reasoning: str
    winner_id: UUID | None
    result: str


class MatchResponse(BaseModel):
    id: UUID
    topic_id: UUID
    topic_title: str
    agent_a: AgentSummary
    agent_b: AgentSummary
    status: str
    winner_id: UUID | None
    score_a: int
    score_b: int
    penalty_a: int
    penalty_b: int
    turn_count: int = 0
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    items: list[MatchResponse]
    total: int


class MatchStreamEvent(BaseModel):
    """SSE로 전송되는 이벤트."""
    event: str  # turn, penalty, finished, error
    data: dict
