import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateTournament(Base):
    __tablename__ = "debate_tournaments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="registration")
    bracket_size: Mapped[int] = mapped_column(Integer, nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    winner_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    topic = relationship("DebateTopic", foreign_keys=[topic_id])
    creator = relationship("User", foreign_keys=[created_by])
    winner_agent = relationship("DebateAgent", foreign_keys=[winner_agent_id])
    entries = relationship("DebateTournamentEntry", back_populates="tournament", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('registration', 'in_progress', 'completed', 'cancelled')",
            name="ck_debate_tournaments_status",
        ),
        CheckConstraint(
            "bracket_size IN (4, 8, 16)",
            name="ck_debate_tournaments_bracket_size",
        ),
    )


# --- DebateTournamentEntry ---

class DebateTournamentEntry(Base):
    __tablename__ = "debate_tournament_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_tournaments.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    eliminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eliminated_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    tournament = relationship("DebateTournament", back_populates="entries")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])
