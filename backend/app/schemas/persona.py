from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PersonaCreate(BaseModel):
    persona_key: str = Field(..., min_length=1, max_length=50)
    version: str = Field(default="v1.0", max_length=20)
    display_name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    system_prompt: str = Field(..., min_length=1, max_length=10000)
    style_rules: dict
    safety_rules: dict = {}
    review_template: dict | None = None
    catchphrases: list[str] | None = None
    greeting_message: str | None = Field(default=None, max_length=5000)
    scenario: str | None = Field(default=None, max_length=5000)
    example_dialogues: list[dict] | None = None
    tags: list[str] | None = None
    category: str | None = None
    live2d_model_id: UUID | None = None
    background_image_url: str | None = Field(default=None, max_length=500)
    age_rating: str = "all"
    visibility: str = "private"
    is_anonymous: bool = False

    @field_validator("age_rating")
    @classmethod
    def validate_age_rating(cls, v: str) -> str:
        if v not in ("all", "15+", "18+"):
            raise ValueError("age_rating must be 'all', '15+', or '18+'")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in ("private", "public", "unlisted"):
            raise ValueError("visibility must be 'private', 'public', or 'unlisted'")
        return v


class PersonaUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    system_prompt: str | None = Field(default=None, max_length=10000)
    style_rules: dict | None = None
    safety_rules: dict | None = None
    review_template: dict | None = None
    catchphrases: list[str] | None = None
    greeting_message: str | None = Field(default=None, max_length=5000)
    scenario: str | None = Field(default=None, max_length=5000)
    example_dialogues: list[dict] | None = None
    tags: list[str] | None = None
    category: str | None = None
    live2d_model_id: UUID | None = None
    background_image_url: str | None = Field(default=None, max_length=500)
    age_rating: str | None = None
    visibility: str | None = None
    is_anonymous: bool | None = None

    @field_validator("age_rating")
    @classmethod
    def validate_age_rating(cls, v: str | None) -> str | None:
        if v is not None and v not in ("all", "15+", "18+"):
            raise ValueError("age_rating must be 'all', '15+', or '18+'")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str | None) -> str | None:
        if v is not None and v not in ("private", "public", "unlisted"):
            raise ValueError("visibility must be 'private', 'public', or 'unlisted'")
        return v


class PersonaResponse(BaseModel):
    id: UUID
    created_by: UUID | None
    type: str
    visibility: str
    moderation_status: str
    age_rating: str
    persona_key: str
    version: str
    display_name: str | None
    description: str | None
    system_prompt: str
    style_rules: dict
    safety_rules: dict
    review_template: dict | None
    catchphrases: list[str] | None
    greeting_message: str | None
    scenario: str | None
    example_dialogues: dict | None
    tags: list[str] | None
    category: str | None
    chat_count: int
    like_count: int
    live2d_model_id: UUID | None
    background_image_url: str | None
    is_active: bool
    is_anonymous: bool
    creator_nickname: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonaListResponse(BaseModel):
    items: list[PersonaResponse]
    total: int


class PersonaStatItem(BaseModel):
    persona_id: str
    display_name: str | None
    chat_count: int
    like_count: int
    age_rating: str
    visibility: str
    moderation_status: str
    created_at: str


class PersonaStatsResponse(BaseModel):
    personas: list[PersonaStatItem]
    total: int
