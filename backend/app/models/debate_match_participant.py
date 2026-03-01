import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateMatchParticipant(Base):
    __tablename__ = "debate_match_participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped[str] = mapped_column(String(1), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)

    agent = relationship("DebateAgent", foreign_keys=[agent_id])
    version = relationship("DebateAgentVersion", foreign_keys=[version_id])

    __table_args__ = (
        CheckConstraint("team IN ('A', 'B')", name="ck_debate_match_participants_team"),
    )
