from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorldEventCreate(BaseModel):
    title: str = Field(max_length=200)
    content: str = Field(min_length=1)
    event_type: str = Field(default="world_state", pattern="^(world_state|seasonal|crisis|lore_update)$")
    priority: int = Field(default=0, ge=0, le=100)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    age_rating: str = Field(default="all", pattern="^(all|15\\+|18\\+)$")


class WorldEventUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    content: str | None = None
    event_type: str | None = Field(None, pattern="^(world_state|seasonal|crisis|lore_update)$")
    priority: int | None = Field(None, ge=0, le=100)
    is_active: bool | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    age_rating: str | None = Field(None, pattern="^(all|15\\+|18\\+)$")


class WorldEventResponse(BaseModel):
    id: UUID
    created_by: UUID | None = None
    title: str
    content: str
    event_type: str
    priority: int
    is_active: bool
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    age_rating: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorldEventListResponse(BaseModel):
    items: list[WorldEventResponse]
    total: int
