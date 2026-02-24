import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateAgent(Base):
    __tablename__ = "debate_agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Fernet 암호화된 API 키 (local 에이전트는 API 키 불필요)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 템플릿 기반 에이전트: 선택한 템플릿 ID
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_agent_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 템플릿 커스터마이징 값 (flat dict: {"aggression": 4, "tone": "formal", ...})
    customizations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1500")
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    is_platform: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    template = relationship("DebateAgentTemplate", foreign_keys=[template_id])
    versions = relationship(
        "DebateAgentVersion", back_populates="agent", cascade="all, delete-orphan",
        order_by="DebateAgentVersion.version_number.desc()"
    )

    __table_args__ = (
        CheckConstraint(
            "provider IN ('openai', 'anthropic', 'google', 'runpod', 'local')",
            name="ck_debate_agents_provider",
        ),
    )
