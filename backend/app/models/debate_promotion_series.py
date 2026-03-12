import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebatePromotionSeries(Base):
    __tablename__ = "debate_promotion_series"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    series_type: Mapped[str] = mapped_column(String(20), nullable=False)
    from_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    to_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    required_wins: Mapped[int] = mapped_column(Integer, nullable=False)
    current_wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    current_losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draw_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("DebateAgent", foreign_keys=[agent_id])

    __table_args__ = (
        CheckConstraint(
            "series_type IN ('promotion', 'demotion')",
            name="ck_promotion_series_type",
        ),
        CheckConstraint(
            "status IN ('active', 'won', 'lost', 'cancelled', 'expired')",
            name="ck_promotion_series_status",
        ),
    )
