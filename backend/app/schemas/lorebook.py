from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LorebookCreate(BaseModel):
    persona_id: UUID | None = None
    webtoon_id: UUID | None = None
    title: str
    content: str
    tags: list[str] | None = None


class LorebookUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


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
