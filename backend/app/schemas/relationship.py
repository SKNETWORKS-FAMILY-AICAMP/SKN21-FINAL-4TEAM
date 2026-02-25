from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RelationshipResponse(BaseModel):
    id: UUID
    user_id: UUID
    persona_id: UUID
    affection_level: int
    relationship_stage: str
    interaction_count: int
    last_interaction_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RelationshipWithPersonaResponse(BaseModel):
    id: UUID
    persona_id: UUID
    persona_display_name: str
    persona_background_image_url: str | None
    affection_level: int
    relationship_stage: str
    interaction_count: int
    last_interaction_at: datetime | None

    model_config = {"from_attributes": False}
