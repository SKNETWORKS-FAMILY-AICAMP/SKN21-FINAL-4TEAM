from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    # 템플릿 기반 생성 파라미터
    template_id: UUID | None = None
    customizations: dict | None = None
    enable_free_text: bool = False


class AgentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    provider: str | None = Field(None, pattern="^(openai|anthropic|google|runpod|local)$")
    model_id: str | None = Field(None, min_length=1, max_length=100)
    api_key: str | None = Field(None, min_length=1)
    system_prompt: str | None = None
    version_tag: str | None = None
    parameters: dict | None = None
    image_url: str | None = None
    is_system_prompt_public: bool | None = None
    # 템플릿 커스터마이징 변경
    customizations: dict | None = None
    enable_free_text: bool = False


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
    is_active: bool
    is_platform: bool = False
    is_connected: bool = False
    is_system_prompt_public: bool = False
    name_changed_at: datetime | None = None
    template_id: UUID | None
    customizations: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
    is_active: bool
    is_platform: bool = False
    is_connected: bool = False
    is_system_prompt_public: bool = False
    system_prompt: str | None = None  # is_system_prompt_public=True일 때만 채워짐
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}
