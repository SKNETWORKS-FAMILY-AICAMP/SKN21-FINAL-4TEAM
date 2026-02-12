import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CommentStat(Base):
    __tablename__ = "comment_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, server_default="0")
    positive_ratio: Mapped[float | None] = mapped_column(Float)
    negative_ratio: Mapped[float | None] = mapped_column(Float)
    top_emotions: Mapped[dict | None] = mapped_column(JSONB)
    toxicity_score: Mapped[float | None] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    episode = relationship("Episode", back_populates="comment_stats")

    __table_args__ = (
        CheckConstraint("toxicity_score BETWEEN 0 AND 1", name="ck_comment_toxicity"),
    )
