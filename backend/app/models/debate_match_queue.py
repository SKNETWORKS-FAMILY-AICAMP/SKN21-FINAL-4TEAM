import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateMatchQueue(Base):
    __tablename__ = "debate_match_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    is_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Relationships
    topic = relationship("DebateTopic", back_populates="queue_entries")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("topic_id", "agent_id", name="uq_debate_queue_topic_agent"),
        Index("idx_debate_queue_user_id", "user_id"),
        Index("idx_debate_queue_agent_id", "agent_id"),
    )
