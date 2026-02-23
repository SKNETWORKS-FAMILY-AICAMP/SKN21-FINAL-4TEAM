import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PendingPost(Base):
    """수동 모드 승인 큐 — publishing_mode='manual'인 캐릭터의 AI 생성 콘텐츠를 소유자 승인 대기."""

    __tablename__ = "pending_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    target_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_posts.id", ondelete="SET NULL")
    )
    target_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_comments.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default="0")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    persona = relationship("Persona", foreign_keys=[persona_id])
    owner = relationship("User", foreign_keys=[owner_user_id])

    __table_args__ = (
        CheckConstraint("content_type IN ('post', 'comment')", name="ck_pending_content_type"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_pending_status"),
        Index("idx_pending_owner_status", "owner_user_id", "status", "created_at"),
        Index("idx_pending_persona_status", "persona_id", "status"),
    )
