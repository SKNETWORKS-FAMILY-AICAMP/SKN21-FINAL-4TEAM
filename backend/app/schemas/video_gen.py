from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class KeyframeInput(BaseModel):
    image_url: str
    frame_index: int = Field(ge=0)
    strength: float = Field(default=0.8, ge=0.0, le=1.0)


class VideoGenCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    negative_prompt: str | None = None
    width: int = Field(default=768, ge=256, le=1920)
    height: int = Field(default=512, ge=256, le=1080)
    num_frames: int = Field(default=97, ge=9, le=257)
    frame_rate: int = Field(default=24, ge=8, le=60)
    num_inference_steps: int = Field(default=40, ge=4, le=100)
    guidance_scale: float = Field(default=3.0, ge=1.0, le=10.0)
    seed: int | None = None
    model_variant: str = Field(default="dev")
    keyframes: list[KeyframeInput] = Field(default_factory=list, max_length=5)

    @field_validator("num_frames")
    @classmethod
    def validate_num_frames(cls, v: int) -> int:
        if (v - 1) % 8 != 0:
            raise ValueError("num_frames must be 8n+1 (e.g., 9, 17, 25, ..., 97, 257)")
        return v

    @field_validator("model_variant")
    @classmethod
    def validate_variant(cls, v: str) -> str:
        if v not in ("dev", "distilled"):
            raise ValueError("model_variant must be 'dev' or 'distilled'")
        return v


class VideoGenResponse(BaseModel):
    id: UUID
    created_by: UUID
    prompt: str
    negative_prompt: str | None
    width: int
    height: int
    num_frames: int
    frame_rate: int
    num_inference_steps: int
    guidance_scale: float
    seed: int | None
    model_variant: str
    keyframes: list[dict] | None
    status: str
    runpod_job_id: str | None
    result_video_url: str | None
    result_metadata: dict | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class VideoGenListResponse(BaseModel):
    items: list[VideoGenResponse]
    total: int
