from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JoinQueueRequest(BaseModel):
    agent_id: UUID = Field(...)
    password: str | None = None


class AgentSummary(BaseModel):
    id: UUID
    name: str
    provider: str
    model_id: str
    elo_rating: int
    image_url: str | None = None

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
    review_result: dict | None = None
    is_blocked: bool = False
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
    elo_a_before: int | None = None
    elo_b_before: int | None = None
    elo_a_after: int | None = None
    elo_b_after: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchListResponse(BaseModel):
    items: list[MatchResponse]
    total: int


class MatchStreamEvent(BaseModel):
    """SSE로 전송되는 이벤트."""
    event: str  # turn, penalty, finished, error
    data: dict


class PredictionCreate(BaseModel):
    prediction: str = Field(..., pattern="^(a_win|b_win|draw)$")


class PredictionStats(BaseModel):
    a_win: int = 0
    b_win: int = 0
    draw: int = 0
    total: int = 0
    my_prediction: str | None = None
    is_correct: bool | None = None
