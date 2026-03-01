from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SeasonCreate(BaseModel):
    season_number: int
    title: str
    start_at: datetime
    end_at: datetime


class SeasonResponse(BaseModel):
    id: UUID
    season_number: int
    title: str
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SeasonResultResponse(BaseModel):
    rank: int
    agent_id: UUID
    agent_name: str
    agent_image_url: str | None = None
    final_elo: int
    final_tier: str
    wins: int
    losses: int
    draws: int
    reward_credits: int
