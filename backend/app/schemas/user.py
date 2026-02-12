from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserCreate(BaseModel):
    nickname: str
    password: str
    email: str | None = None


class UserLogin(BaseModel):
    nickname: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    nickname: str
    role: str
    age_group: str
    adult_verified_at: datetime | None = None
    preferred_llm_model_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
