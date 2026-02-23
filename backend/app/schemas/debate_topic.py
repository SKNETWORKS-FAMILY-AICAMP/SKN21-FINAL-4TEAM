from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    mode: str = Field("debate", pattern="^(debate|persuasion|cross_exam)$")
    max_turns: int = Field(6, ge=2, le=20)
    turn_token_limit: int = Field(500, ge=100, le=2000)


class TopicUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = Field(None, pattern="^(open|in_progress|closed)$")
    max_turns: int | None = Field(None, ge=2, le=20)
    turn_token_limit: int | None = Field(None, ge=100, le=2000)


class TopicResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    mode: str
    status: str
    max_turns: int
    turn_token_limit: int
    queue_count: int = 0
    match_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    items: list[TopicResponse]
    total: int
