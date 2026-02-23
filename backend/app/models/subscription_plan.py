import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    plan_key: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_krw: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    daily_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    credit_rollover_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_lounge_personas: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    max_agent_actions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    features: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
