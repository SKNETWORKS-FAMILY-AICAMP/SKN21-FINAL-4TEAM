"""사용량 할당(quota) 모델."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UsageQuota(Base):
    __tablename__ = "usage_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # 일일 한도
    daily_token_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100_000)
    # 월간 한도
    monthly_token_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2_000_000)
    # 월간 비용 한도 ($)
    monthly_cost_limit: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=10.0)

    # 할당 활성 여부 (관리자가 비활성화 가능)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=datetime.now
    )

    user = relationship("User")
