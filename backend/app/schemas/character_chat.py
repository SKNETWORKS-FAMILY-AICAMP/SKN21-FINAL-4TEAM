from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequestCreate(BaseModel):
    requester_persona_id: UUID
    responder_persona_id: UUID
    max_turns: int = Field(default=10, ge=1, le=20)
    is_public: bool = True


class ChatRequestRespond(BaseModel):
    accept: bool


class ChatParticipant(BaseModel):
    persona_id: UUID
    display_name: str
    owner_id: UUID


class ChatSessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    requester: ChatParticipant
    responder: ChatParticipant
    status: str
    max_turns: int
    current_turn: int
    is_public: bool
    age_rating: str
    total_cost: float
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionResponse]
    total: int


class ChatMessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    persona_id: UUID
    persona_display_name: str
    content: str
    turn_number: int
    created_at: datetime


class ChatDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]
