from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ── 게시판 ──


class BoardResponse(BaseModel):
    id: UUID
    board_key: str
    display_name: str
    description: str | None = None
    age_rating: str
    is_active: bool

    model_config = {"from_attributes": True}


# ── 게시글 ──


class PostCreate(BaseModel):
    title: str | None = Field(None, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    persona_id: UUID | None = None
    age_rating: str = "all"


class PostAuthor(BaseModel):
    type: str  # 'user' | 'persona'
    id: UUID
    display_name: str


class PostResponse(BaseModel):
    id: UUID
    board_id: UUID
    title: str | None = None
    content: str
    author: PostAuthor
    age_rating: str
    is_ai_generated: bool
    reaction_count: int
    comment_count: int
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    my_reaction: str | None = None


class PostListResponse(BaseModel):
    items: list[PostResponse]
    total: int


# ── 댓글 ──


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_id: UUID | None = None
    persona_id: UUID | None = None


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    parent_id: UUID | None = None
    author: PostAuthor
    content: str
    is_ai_generated: bool
    reaction_count: int
    created_at: datetime
    my_reaction: str | None = None
    children: list["CommentResponse"] = []


class PostDetailResponse(BaseModel):
    post: PostResponse
    comments: list[CommentResponse]


# ── 리액션 ──


class ReactionRequest(BaseModel):
    reaction_type: str = "like"


class ReactionResponse(BaseModel):
    toggled: bool
    new_count: int
