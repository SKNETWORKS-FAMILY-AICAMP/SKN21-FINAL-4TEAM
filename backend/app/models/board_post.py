import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BoardPost(Base):
    """게시글."""

    __tablename__ = "board_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("boards.id"), nullable=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    author_persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    age_rating: Mapped[str] = mapped_column(String(20), nullable=False, server_default="all")
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    reaction_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    character_chat_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("character_chat_sessions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    author_user = relationship("User", foreign_keys=[author_user_id])
    author_persona = relationship("Persona", foreign_keys=[author_persona_id])
    board = relationship("Board", foreign_keys=[board_id])
    comments = relationship("BoardComment", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "author_user_id IS NOT NULL OR author_persona_id IS NOT NULL",
            name="ck_post_author",
        ),
        CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_post_age_rating"),
        Index("idx_posts_board", "board_id", "created_at"),
        Index("idx_posts_persona", "author_persona_id", "created_at"),
        Index("idx_posts_user", "author_user_id", "created_at"),
    )
