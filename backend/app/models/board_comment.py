import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BoardComment(Base):
    """게시글 댓글/답글 (트리 구조)."""

    __tablename__ = "board_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_posts.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_comments.id", ondelete="CASCADE")
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    author_persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    reaction_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    post = relationship("BoardPost", back_populates="comments", foreign_keys=[post_id])
    parent = relationship("BoardComment", remote_side="BoardComment.id", foreign_keys=[parent_id])
    author_user = relationship("User", foreign_keys=[author_user_id])
    author_persona = relationship("Persona", foreign_keys=[author_persona_id])

    __table_args__ = (
        CheckConstraint(
            "author_user_id IS NOT NULL OR author_persona_id IS NOT NULL",
            name="ck_comment_author",
        ),
        Index("idx_comments_post", "post_id", "created_at"),
        Index("idx_comments_parent", "parent_id"),
    )
