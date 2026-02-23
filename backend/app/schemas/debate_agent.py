from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    provider: str = Field(..., pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str = Field("custom", min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str = Field(..., min_length=1)
    version_tag: str | None = None
    parameters: dict | None = None


class AgentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    provider: str | None = Field(None, pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str | None = None
    version_tag: str | None = None
    parameters: dict | None = None


class AgentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    version_tag: str | None
    system_prompt: str
    parameters: dict | None
    wins: int
    losses: int
    draws: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    provider: str
    model_id: str
    elo_rating: int
    wins: int
    losses: int
    draws: int
    is_active: bool
    is_connected: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRankingResponse(BaseModel):
    id: UUID
    name: str
    owner_nickname: str
    provider: str
    model_id: str
    elo_rating: int
    wins: int
    losses: int
    draws: int

    model_config = {"from_attributes": True}
