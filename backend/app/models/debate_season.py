import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateSeason(Base):
    __tablename__ = "debate_seasons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="upcoming")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    results = relationship("DebateSeasonResult", back_populates="season", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('upcoming', 'active', 'completed')",
            name="ck_debate_seasons_status",
        ),
    )
