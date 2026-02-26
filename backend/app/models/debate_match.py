import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateMatch(Base):
    __tablename__ = "debate_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    agent_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_a_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL")
    )
    agent_b_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    winner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # 스코어카드: {agent_a: {logic: 28, evidence: 22, ...}, agent_b: {...}, reasoning: "..."}
    scorecard: Mapped[dict | None] = mapped_column(JSONB)
    score_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    score_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elo_a_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_b_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_a_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_b_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    topic = relationship("DebateTopic", back_populates="matches")
    agent_a = relationship("DebateAgent", foreign_keys=[agent_a_id])
    agent_b = relationship("DebateAgent", foreign_keys=[agent_b_id])
    agent_a_version = relationship("DebateAgentVersion", foreign_keys=[agent_a_version_id])
    agent_b_version = relationship("DebateAgentVersion", foreign_keys=[agent_b_version_id])
    turns = relationship(
        "DebateTurnLog", back_populates="match", cascade="all, delete-orphan",
        order_by="DebateTurnLog.turn_number"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'error', 'waiting_agent', 'forfeit')",
            name="ck_debate_matches_status",
        ),
    )
