import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    login_id: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email_hash: Mapped[str | None] = mapped_column(String(64))
    password_hash: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    age_group: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unverified")
    adult_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_method: Mapped[str | None] = mapped_column(String(20))
    preferred_llm_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_models.id"))
    preferred_themes: Mapped[list[str] | None] = mapped_column(ARRAY(String(30)), nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_credit_grant_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships - only keep relationships to models that exist
    preferred_llm_model = relationship("LLMModel", foreign_keys=[preferred_llm_model_id])

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin', 'superadmin')", name="ck_users_role"),
        CheckConstraint("age_group IN ('minor_safe', 'adult_verified', 'unverified')", name="ck_users_age_group"),
    )
