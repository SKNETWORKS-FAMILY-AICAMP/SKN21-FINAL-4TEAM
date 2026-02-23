from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FavoriteResponse(BaseModel):
    id: UUID
    user_id: UUID
    persona_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteWithPersonaResponse(BaseModel):
    id: UUID
    persona_id: UUID
    persona_display_name: str
    persona_description: str | None
    persona_age_rating: str
    persona_background_image_url: str | None
    persona_chat_count: int
    persona_like_count: int
    persona_tags: list[str] | None
    created_at: datetime
