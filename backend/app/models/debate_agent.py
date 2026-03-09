import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
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
    # 이름 변경 제한 (7일 1회)
    name_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 시스템 프롬프트 공개 여부 (소유자 결정)
    is_system_prompt_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # 플랫폼 크레딧으로 API 비용 지불 (BYOK API 키 불필요)
    use_platform_credits: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Iron")
    tier_protection_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 활성 승급전/강등전 시리즈 (매칭 시 빠른 조회용)
    active_series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_promotion_series.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_profile_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
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


# --- DebateAgentVersion ---

class DebateAgentVersion(Base):
    __tablename__ = "debate_agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_tag: Mapped[str | None] = mapped_column(String(50))
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    agent = relationship("DebateAgent", back_populates="versions")


# --- DebateAgentSeasonStats ---

class DebateAgentSeasonStats(Base):
    __tablename__ = "debate_agent_season_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_seasons.id", ondelete="CASCADE"), nullable=False
    )
    # 시즌 ELO: 매 시즌 1500으로 초기화
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1500")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Iron")
    wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()")
    )

    agent = relationship("DebateAgent")
    season = relationship("DebateSeason")

    __table_args__ = (
        # 에이전트당 시즌당 1행
        UniqueConstraint("agent_id", "season_id", name="uq_season_stats_agent_season"),
    )
