from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LorebookCreate(BaseModel):
    persona_id: UUID | None = None
    webtoon_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=20000)
    tags: list[str] | None = Field(default=None, max_length=20)


class LorebookUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=20000)
    tags: list[str] | None = Field(default=None, max_length=20)


class LorebookResponse(BaseModel):
    id: int
    persona_id: UUID | None
    webtoon_id: UUID | None
    created_by: UUID
    title: str
    content: str
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LorebookListResponse(BaseModel):
    items: list[LorebookResponse]
    total: int
