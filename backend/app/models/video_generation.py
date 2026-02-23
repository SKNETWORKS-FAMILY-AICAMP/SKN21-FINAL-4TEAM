import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VideoGeneration(Base):
    """LTX-Video 13B 영상 생성 작업 추적."""

    __tablename__ = "video_generations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Generation parameters
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer, nullable=False, server_default="768")
    height: Mapped[int] = mapped_column(Integer, nullable=False, server_default="512")
    num_frames: Mapped[int] = mapped_column(Integer, nullable=False, server_default="97")
    frame_rate: Mapped[int] = mapped_column(Integer, nullable=False, server_default="24")
    num_inference_steps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="40")
    guidance_scale: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, server_default="3.0")
    seed: Mapped[int | None] = mapped_column(BigInteger)
    model_variant: Mapped[str] = mapped_column(String(20), nullable=False, server_default="dev")

    # Keyframe images — [{image_url, frame_index, strength}] 최대 5개
    keyframes: Mapped[list | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))

    # Job tracking
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    runpod_job_id: Mapped[str | None] = mapped_column(String(100))

    # Result
    result_video_url: Mapped[str | None] = mapped_column(String(500))
    result_metadata: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'submitted', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_video_gen_status",
        ),
        CheckConstraint(
            "model_variant IN ('dev', 'distilled')",
            name="ck_video_gen_variant",
        ),
        CheckConstraint(
            text("(num_frames - 1) % 8 = 0 AND num_frames >= 9"),
            name="ck_video_gen_frames",
        ),
    )
