from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    persona_id: UUID
    webtoon_id: UUID | None = None
    llm_model_id: UUID | None = None
    user_persona_id: UUID | None = None


class SessionResponse(BaseModel):
    id: UUID
    persona_id: UUID
    llm_model_id: UUID | None
    webtoon_id: UUID | None
    user_persona_id: UUID | None
    title: str | None
    is_pinned: bool
    status: str
    started_at: datetime
    last_active_at: datetime
    persona_display_name: str | None = None
    persona_background_image_url: str | None = None
    persona_age_rating: str | None = None
    persona_category: str | None = None

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    session_id: UUID
    role: str
    content: str
    token_count: int | None
    emotion_signal: dict | None
    parent_id: int | None
    is_active: bool
    is_edited: bool
    edited_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    is_pinned: bool | None = None
    llm_model_id: UUID | None = None


class MessageUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class SiblingResponse(BaseModel):
    messages: list[MessageResponse]
    current_index: int
    total: int
