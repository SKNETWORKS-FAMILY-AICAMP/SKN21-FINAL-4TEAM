import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMModel(Base):
    __tablename__ = "llm_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_cost_per_1m: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    output_cost_per_1m: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    max_context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    is_adult_only: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="economy")
    credit_per_1k_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("provider", "model_id", name="uq_llm_provider_model"),
        CheckConstraint("tier IN ('economy', 'standard', 'premium')", name="ck_llm_tier"),
    )
