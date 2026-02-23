import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PersonaRelationship(Base):
    __tablename__ = "persona_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False
    )
    affection_level: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    relationship_stage: Mapped[str] = mapped_column(String(30), server_default="stranger", nullable=False)
    interaction_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    user = relationship("User", back_populates="relationships")
    persona = relationship("Persona", back_populates="relationships")

    __table_args__ = (
        UniqueConstraint("user_id", "persona_id", name="uq_relationship_user_persona"),
        CheckConstraint(
            "relationship_stage IN ('stranger','acquaintance','friend','close_friend','crush','lover','soulmate')",
            name="ck_relationship_stage",
        ),
        CheckConstraint("affection_level BETWEEN 0 AND 1000", name="ck_affection_range"),
        Index("idx_relationships_user", "user_id"),
    )
