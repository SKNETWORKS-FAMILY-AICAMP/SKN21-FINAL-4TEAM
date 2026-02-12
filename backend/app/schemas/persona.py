from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PersonaCreate(BaseModel):
    persona_key: str
    version: str = "v1.0"
    display_name: str | None = None
    system_prompt: str
    style_rules: dict
    safety_rules: dict = {}
    review_template: dict | None = None
    catchphrases: list[str] | None = None
    live2d_model_id: UUID | None = None
    background_image_url: str | None = None
    age_rating: str = "all"
    visibility: str = "private"


class PersonaUpdate(BaseModel):
    display_name: str | None = None
    system_prompt: str | None = None
    style_rules: dict | None = None
    review_template: dict | None = None
    catchphrases: list[str] | None = None
    live2d_model_id: UUID | None = None
    background_image_url: str | None = None
    age_rating: str | None = None
    visibility: str | None = None


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
    system_prompt: str
    style_rules: dict
    live2d_model_id: UUID | None
    background_image_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonaListResponse(BaseModel):
    items: list[PersonaResponse]
    total: int
