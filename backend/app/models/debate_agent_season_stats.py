import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateAgentSeasonStats(Base):
    __tablename__ = "debate_agent_season_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_seasons.id", ondelete="CASCADE"), nullable=False
    )
    # 시즌 ELO: 매 시즌 1500으로 초기화
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1500")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Iron")
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()")
    )

    agent = relationship("DebateAgent")
    season = relationship("DebateSeason")

    __table_args__ = (
        # 에이전트당 시즌당 1행
        UniqueConstraint("agent_id", "season_id", name="uq_season_stats_agent_season"),
    )
