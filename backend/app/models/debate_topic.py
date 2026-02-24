import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateTopic(Base):
    __tablename__ = "debate_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="debate")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, server_default="6")
    turn_token_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="500")
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin_topic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    tools_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    matches = relationship("DebateMatch", back_populates="topic")
    queue_entries = relationship("DebateMatchQueue", back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "mode IN ('debate', 'persuasion', 'cross_exam')",
            name="ck_debate_topics_mode",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'open', 'in_progress', 'closed')",
            name="ck_debate_topics_status",
        ),
    )
