import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateTurnLog(Base):
    __tablename__ = "debate_turn_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    tool_used: Mapped[str | None] = mapped_column(String(50))
    tool_result: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    penalties: Mapped[dict | None] = mapped_column(JSONB)
    penalty_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    review_result: Mapped[dict | None] = mapped_column(JSONB)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    human_suspicion_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    match = relationship("DebateMatch", back_populates="turns")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])

    __table_args__ = (
        CheckConstraint(
            "speaker IN ('agent_a', 'agent_b')",
            name="ck_debate_turn_logs_speaker",
        ),
        CheckConstraint(
            "action IN ('argue', 'rebut', 'concede', 'question', 'summarize')",
            name="ck_debate_turn_logs_action",
        ),
    )
