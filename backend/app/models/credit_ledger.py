import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_LEDGER_TX_TYPES = (
    "'daily_grant','purchase','chat','lounge_post','lounge_comment',"
    "'review','agent_action','expire','admin_grant','refund'"
)


class CreditLedger(Base):
    """대화석 거래 원장. append-only — UPDATE/DELETE 금지."""

    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        CheckConstraint(
            f"tx_type IN ({_LEDGER_TX_TYPES})",
            name="ck_ledger_tx_type",
        ),
        Index("idx_ledger_user", "user_id", "created_at"),
    )
