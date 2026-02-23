from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CharacterPageStats(BaseModel):
    post_count: int
    follower_count: int
    like_count: int
    chat_count: int


class CharacterPageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    display_name: str
    description: str | None = None
    greeting_message: str | None = None
    age_rating: str
    category: str | None = None
    tags: list[str] | None = None
    background_image_url: str | None = None
    live2d_model_id: UUID | None = None
    creator_name: str | None = None
    stats: CharacterPageStats
    is_following: bool = False
    created_at: datetime


class FollowResponse(BaseModel):
    following: bool
    follower_count: int


class FollowerItem(BaseModel):
    model_config = {"from_attributes": True}

    user_id: UUID
    nickname: str
    followed_at: datetime


class FollowerListResponse(BaseModel):
    items: list[FollowerItem]
    total: int
