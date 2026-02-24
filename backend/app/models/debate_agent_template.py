import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DebateAgentTemplate(Base):
    __tablename__ = "debate_agent_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 관리자만 편집 가능한 코어 프롬프트. {customization_block} 플레이스홀더 포함.
    base_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # 커스터마이징 가능 항목 정의 (sliders, selects, free_text)
    customization_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # 기본값 (flat dict: {"aggression": 3, "tone": "neutral", ...})
    default_values: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
