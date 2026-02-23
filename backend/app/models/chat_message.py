import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    emotion_signal: Mapped[dict | None] = mapped_column(JSONB)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chat_messages.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    session = relationship("ChatSession", back_populates="messages")
    parent = relationship("ChatMessage", remote_side="ChatMessage.id", back_populates="children")
    children = relationship("ChatMessage", back_populates="parent")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_message_role"),
        Index("idx_messages_session", "session_id", "created_at"),
        Index("idx_messages_parent", "parent_id"),
    )
