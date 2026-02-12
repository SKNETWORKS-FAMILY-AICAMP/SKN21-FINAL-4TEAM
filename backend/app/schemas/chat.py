from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionCreate(BaseModel):
    persona_id: UUID
    webtoon_id: UUID | None = None
    llm_model_id: UUID | None = None


class SessionResponse(BaseModel):
    id: UUID
    persona_id: UUID
    llm_model_id: UUID | None
    webtoon_id: UUID | None
    status: str
    started_at: datetime
    last_active_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: UUID
    role: str
    content: str
    token_count: int | None
    emotion_signal: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
