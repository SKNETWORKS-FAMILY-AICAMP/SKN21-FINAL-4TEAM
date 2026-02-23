import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SpoilerSetting(Base):
    __tablename__ = "spoiler_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    webtoon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webtoons.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    max_episode: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    user = relationship("User", back_populates="spoiler_settings")
    webtoon = relationship("Webtoon")

    __table_args__ = (
        CheckConstraint("mode IN ('off', 'theme_only', 'up_to', 'full')", name="ck_spoiler_mode"),
        UniqueConstraint("user_id", "webtoon_id", name="uq_spoiler_user_webtoon"),
    )
