from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TournamentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    topic_id: UUID
    bracket_size: int = Field(..., ge=4, le=16)


class TournamentEntryResponse(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str
    agent_image_url: str | None = None
    seed: int
    eliminated_at: datetime | None = None
    eliminated_round: int | None = None


class TournamentResponse(BaseModel):
    id: UUID
    title: str
    topic_id: UUID
    status: str
    bracket_size: int
    current_round: int
    winner_agent_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    entries: list[TournamentEntryResponse] = []
