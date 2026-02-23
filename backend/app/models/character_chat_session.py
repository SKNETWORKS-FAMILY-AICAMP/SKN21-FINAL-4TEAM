import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CharacterChatSession(Base):
    """캐릭터 간 1:1 대화 세션."""

    __tablename__ = "character_chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    requester_persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    responder_persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    requester_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    responder_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    current_turn: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, server_default="0")
    age_rating: Mapped[str] = mapped_column(String(20), nullable=False, server_default="all")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requester_persona = relationship("Persona", foreign_keys=[requester_persona_id])
    responder_persona = relationship("Persona", foreign_keys=[responder_persona_id])
    requester_owner = relationship("User", foreign_keys=[requester_owner_id])
    responder_owner = relationship("User", foreign_keys=[responder_owner_id])
    messages = relationship(
        "CharacterChatMessage", back_populates="session", cascade="all, delete-orphan",
        order_by="CharacterChatMessage.turn_number",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'rejected', 'cancelled')",
            name="ck_cc_session_status",
        ),
        CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_cc_session_age_rating"),
        CheckConstraint("max_turns BETWEEN 1 AND 20", name="ck_cc_max_turns"),
        Index("idx_cc_requester_status", "requester_persona_id", "status"),
        Index("idx_cc_responder_status", "responder_persona_id", "status"),
        Index("idx_cc_req_owner_status", "requester_owner_id", "status"),
        Index("idx_cc_resp_owner_status", "responder_owner_id", "status"),
        # 같은 캐릭터 쌍 간 동시 active 세션 1개 — partial unique index
        Index(
            "uq_cc_active_pair",
            "requester_persona_id",
            "responder_persona_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
