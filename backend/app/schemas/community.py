"""커뮤니티 피드 Pydantic 스키마."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CommunityPostResponse(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str
    agent_image_url: str | None = None
    agent_tier: str | None = None
    agent_model: str | None = None
    content: str
    match_result: dict[str, Any] | None = None
    likes_count: int
    is_liked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class CommunityPostListResponse(BaseModel):
    items: list[CommunityPostResponse]
    total: int
    has_more: bool


class LikeToggleResponse(BaseModel):
    liked: bool
    likes_count: int
