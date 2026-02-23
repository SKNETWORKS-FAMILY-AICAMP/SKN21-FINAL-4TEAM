import uuid

from sqlalchemy import Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CreditCost(Base):
    """행동 × 모델 등급별 대화석 소비 단가."""

    __tablename__ = "credit_costs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    model_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("action", "model_tier", name="uq_credit_cost"),)
