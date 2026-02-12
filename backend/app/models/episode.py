import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    webtoon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webtoons.id", ondelete="CASCADE"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[date | None] = mapped_column(Date)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    webtoon = relationship("Webtoon", back_populates="episodes")
    emotions = relationship("EpisodeEmotion", back_populates="episode", cascade="all, delete-orphan")
    embeddings = relationship("EpisodeEmbedding", back_populates="episode", cascade="all, delete-orphan")
    comment_stats = relationship("CommentStat", back_populates="episode", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("webtoon_id", "episode_number", name="uq_episode_webtoon_number"),
    )
