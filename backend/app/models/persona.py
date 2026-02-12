import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user_created")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="private")
    moderation_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    age_rating: Mapped[str] = mapped_column(String(20), nullable=False, server_default="all")
    persona_key: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    style_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    safety_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    review_template: Mapped[dict | None] = mapped_column(JSONB)
    catchphrases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    live2d_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("live2d_models.id"))
    background_image_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    creator = relationship("User", back_populates="personas", foreign_keys=[created_by])
    live2d_model = relationship("Live2DModel")
    lorebook_entries = relationship("LorebookEntry", back_populates="persona", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("type IN ('system', 'user_created')", name="ck_personas_type"),
        CheckConstraint("visibility IN ('private', 'public', 'unlisted')", name="ck_personas_visibility"),
        CheckConstraint("moderation_status IN ('pending', 'approved', 'blocked')", name="ck_personas_moderation"),
        CheckConstraint("age_rating IN ('all', '15+', '18+')", name="ck_personas_age_rating"),
        UniqueConstraint("persona_key", "version", name="uq_persona_key_version"),
        Index("idx_personas_created_by", "created_by"),
        Index("idx_personas_type_visibility", "type", "visibility"),
        Index("idx_personas_moderation", "moderation_status"),
    )
