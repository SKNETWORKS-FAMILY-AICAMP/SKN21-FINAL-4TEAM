from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoungeConfigResponse(BaseModel):
    persona_id: UUID
    is_active: bool
    activity_level: str
    interest_tags: list[str]
    allowed_boards: list[UUID]
    daily_action_limit: int
    actions_today: int
    last_action_at: datetime | None = None
    # 캐릭터 페이지 설정
    publishing_mode: str = "auto"
    daily_post_limit: int = 3
    daily_comment_limit: int = 10
    daily_chat_limit: int = 2
    posts_today: int = 0
    comments_today: int = 0
    chats_today: int = 0
    auto_comment_reply: bool = True
    accept_chat_requests: bool = True
    auto_accept_chats: bool = False

    model_config = {"from_attributes": True}


class LoungeConfigUpdate(BaseModel):
    activity_level: str | None = Field(None, pattern="^(quiet|normal|active)$")
    interest_tags: list[str] | None = None
    allowed_boards: list[UUID] | None = None
    publishing_mode: str | None = Field(None, pattern="^(auto|manual)$")
    daily_post_limit: int | None = Field(None, ge=0, le=50)
    daily_comment_limit: int | None = Field(None, ge=0, le=100)
    daily_chat_limit: int | None = Field(None, ge=0, le=20)
    auto_comment_reply: bool | None = None
    accept_chat_requests: bool | None = None
    auto_accept_chats: bool | None = None


class AgentActivityResponse(BaseModel):
    id: int
    persona_id: UUID
    action_type: str
    target_post_id: UUID | None = None
    result_post_id: UUID | None = None
    result_comment_id: UUID | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentActivityListResponse(BaseModel):
    items: list[AgentActivityResponse]
    total: int


class AdminAgentSummary(BaseModel):
    total_actions_today: int
    total_actions_all: int
    active_personas: int
    total_tokens_today: int
    total_cost_today: float
