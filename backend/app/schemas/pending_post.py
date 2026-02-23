from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PendingPostResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    persona_id: UUID
    persona_display_name: str | None = None
    content_type: str
    title: str | None = None
    content: str
    target_post_id: UUID | None = None
    target_comment_id: UUID | None = None
    status: str
    input_tokens: int
    output_tokens: int
    cost: float
    created_at: datetime
    reviewed_at: datetime | None = None


class PendingPostListResponse(BaseModel):
    items: list[PendingPostResponse]
    total: int


class PendingPostAction(BaseModel):
    action: str  # 'approve' | 'reject'
