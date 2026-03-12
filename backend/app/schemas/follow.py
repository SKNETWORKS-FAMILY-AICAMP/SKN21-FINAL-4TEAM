from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FollowCreate(BaseModel):
    target_type: Literal["user", "agent"]
    target_id: UUID


class FollowResponse(BaseModel):
    id: UUID
    target_type: str
    target_id: UUID
    target_name: str
    target_image_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowListResponse(BaseModel):
    items: list[FollowResponse]
    total: int
