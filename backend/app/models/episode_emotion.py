import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EpisodeEmotion(Base):
    __tablename__ = "episode_emotions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    emotion_label: Mapped[str] = mapped_column(String(30), nullable=False)
    intensity: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    episode = relationship("Episode", back_populates="emotions")

    __table_args__ = (
        CheckConstraint("intensity BETWEEN 0 AND 1", name="ck_emotion_intensity"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_emotion_confidence"),
        UniqueConstraint("episode_id", "emotion_label", "model_version", name="uq_emotion_episode_label_version"),
        Index("idx_emotions_episode", "episode_id"),
    )
