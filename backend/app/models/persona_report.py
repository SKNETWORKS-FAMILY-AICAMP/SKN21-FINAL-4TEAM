import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PersonaReport(Base):
    __tablename__ = "persona_reports"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    admin_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    persona = relationship("Persona", foreign_keys=[persona_id])
    reporter = relationship("User", foreign_keys=[reporter_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        CheckConstraint(
            "reason IN ('inappropriate', 'sexual', 'harassment', 'copyright', 'spam', 'other')",
            name="ck_persona_reports_reason",
        ),
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed')",
            name="ck_persona_reports_status",
        ),
        UniqueConstraint("persona_id", "reporter_id", name="uq_persona_report_unique"),
        Index("idx_persona_reports_status", "status"),
        Index("idx_persona_reports_persona_id", "persona_id"),
    )
