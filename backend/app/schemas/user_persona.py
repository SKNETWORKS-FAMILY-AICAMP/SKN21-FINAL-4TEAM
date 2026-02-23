from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserPersonaCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserPersonaUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=500)


class UserPersonaResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    description: str | None
    avatar_url: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
