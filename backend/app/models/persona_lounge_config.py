import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PersonaLoungeConfig(Base):
    """페르소나별 라운지 참여 설정."""

    __tablename__ = "persona_lounge_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    activity_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    interest_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), server_default="{}")
    allowed_boards: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}")
    daily_action_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    actions_today: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 캐릭터 페이지 시스템: 퍼블리싱 모드 및 세분화 한도
    publishing_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="auto")
    daily_post_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    daily_comment_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    daily_chat_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    posts_today: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    comments_today: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chats_today: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    auto_comment_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    accept_chat_requests: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    auto_accept_chats: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    persona = relationship("Persona", foreign_keys=[persona_id])

    __table_args__ = (
        CheckConstraint("activity_level IN ('quiet', 'normal', 'active')", name="ck_lounge_activity"),
        CheckConstraint("publishing_mode IN ('auto', 'manual')", name="ck_lounge_publishing_mode"),
    )
