import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Webtoon(Base):
    __tablename__ = "webtoons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(30))
    genre: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    age_rating: Mapped[str] = mapped_column(String(20), nullable=False)
    total_episodes: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(String(20), server_default="ongoing")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    episodes = relationship("Episode", back_populates="webtoon", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("age_rating IN ('all', '12+', '15+', '18+')", name="ck_webtoons_age_rating"),
    )
