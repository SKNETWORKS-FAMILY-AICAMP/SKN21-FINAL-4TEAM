from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# 템플릿 스키마
# ---------------------------------------------------------------------------

class AgentTemplateResponse(BaseModel):
    """사용자 공개 템플릿 응답 — base_system_prompt 미노출."""

    id: UUID
    slug: str
    display_name: str
    description: str | None
    icon: str | None
    customization_schema: dict
    default_values: dict
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class AgentTemplateAdminResponse(AgentTemplateResponse):
    """관리자 템플릿 응답 — base_system_prompt 포함."""

    base_system_prompt: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentTemplateCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    base_system_prompt: str = Field(..., min_length=1)
    customization_schema: dict
    default_values: dict
    sort_order: int = 0
    is_active: bool = True


class AgentTemplateUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = Field(None, max_length=50)
    base_system_prompt: str | None = Field(None, min_length=1)
    customization_schema: dict | None = None
    default_values: dict | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# 에이전트 스키마
# ---------------------------------------------------------------------------

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    provider: str = Field(..., pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str = Field("custom", min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str | None = Field(None, min_length=1)
    version_tag: str | None = None
    parameters: dict | None = None
    image_url: str | None = None
    is_system_prompt_public: bool = False
    use_platform_credits: bool = False
    # 템플릿 기반 생성 파라미터
    template_id: UUID | None = None
    customizations: dict | None = None
    enable_free_text: bool = False
    is_profile_public: bool = True


class AgentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    provider: str | None = Field(None, pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str | None = Field(None, min_length=1)
    version_tag: str | None = None
    parameters: dict | None = None
    image_url: str | None = None
    is_system_prompt_public: bool | None = None
    use_platform_credits: bool | None = None
    # 템플릿 커스터마이징 변경
    customizations: dict | None = None
    enable_free_text: bool = False
    is_profile_public: bool | None = None


class AgentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    version_tag: str | None
    system_prompt: str
    parameters: dict | None
    wins: int
    losses: int
    draws: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    provider: str
    model_id: str
    image_url: str | None = None
    elo_rating: int
    wins: int
    losses: int
    draws: int
    win_rate: float = 0.0  # wins / total * 100 (소수점 1자리)
    is_active: bool
    is_platform: bool = False
    is_connected: bool = False
    is_system_prompt_public: bool = False
    use_platform_credits: bool = False
    name_changed_at: datetime | None = None
    template_id: UUID | None
    customizations: dict | None
    tier: str = "Iron"
    tier_protection_count: int = 0
    active_series_id: UUID | None = None
    is_profile_public: bool = True
    follower_count: int = 0
    is_following: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_win_rate(self) -> "AgentResponse":
        total = self.wins + self.losses + self.draws
        self.win_rate = round(self.wins / total * 100, 1) if total > 0 else 0.0
        return self


class AgentPublicResponse(BaseModel):
    """비소유자 공개 응답 — customizations 미노출. is_system_prompt_public=True이면 system_prompt 포함."""

    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    provider: str
    model_id: str
    image_url: str | None = None
    elo_rating: int
    wins: int
    losses: int
    draws: int
    win_rate: float = 0.0
    is_active: bool
    is_platform: bool = False
    is_connected: bool = False
    is_system_prompt_public: bool = False
    system_prompt: str | None = None  # is_system_prompt_public=True일 때만 채워짐
    tier: str = "Iron"
    is_profile_public: bool = True
    follower_count: int = 0
    is_following: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_win_rate(self) -> "AgentPublicResponse":
        total = self.wins + self.losses + self.draws
        self.win_rate = round(self.wins / total * 100, 1) if total > 0 else 0.0
        return self


class AgentRankingResponse(BaseModel):
    id: UUID
    name: str
    owner_nickname: str
    provider: str
    model_id: str
    elo_rating: int
    wins: int
    losses: int
    draws: int
    image_url: str | None = None
    tier: str = "Iron"
    is_profile_public: bool = True

    model_config = {"from_attributes": True}


class HeadToHeadEntry(BaseModel):
    opponent_id: str
    opponent_name: str
    opponent_image_url: str | None = None
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float = 0.0

    @model_validator(mode="after")
    def compute_win_rate(self) -> "HeadToHeadEntry":
        total = self.wins + self.losses + self.draws
        self.win_rate = round(self.wins / total * 100, 1) if total > 0 else 0.0
        return self


class GalleryEntry(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    provider: str
    model_id: str
    image_url: str | None = None
    elo_rating: int
    wins: int
    losses: int
    draws: int
    tier: str
    owner_nickname: str
    is_system_prompt_public: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class CloneRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class PromotionSeriesResponse(BaseModel):
    id: UUID
    agent_id: UUID
    series_type: str
    from_tier: str
    to_tier: str
    required_wins: int
    current_wins: int
    current_losses: int
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 페이지네이션 래퍼
# ---------------------------------------------------------------------------

class AgentRankingListResponse(BaseModel):
    items: list[AgentRankingResponse]
    total: int


class GalleryListResponse(BaseModel):
    items: list[GalleryEntry]
    total: int


class HeadToHeadListResponse(BaseModel):
    items: list[HeadToHeadEntry]
