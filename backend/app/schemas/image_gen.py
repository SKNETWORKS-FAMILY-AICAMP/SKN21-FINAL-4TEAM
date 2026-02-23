from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ImageGenCreate(BaseModel):
    """이미지 생성 요청."""

    prompt: str = Field(..., min_length=1, max_length=4000)
    negative_prompt: str | None = None
    style: str | None = None  # None이면 설정 기본값 사용
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    seed: int | None = None


class ImageGenResponse(BaseModel):
    """이미지 생성 결과."""

    image_url: str
    prompt: str
    style: str | None
    width: int
    height: int
    seed: int | None
    provider: str


class ImageGenHistoryItem(BaseModel):
    """이미지 생성 이력 항목."""

    id: int
    image_url: str
    prompt: str
    style: str | None
    provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImageGenHistoryResponse(BaseModel):
    """이미지 생성 이력."""

    items: list[ImageGenHistoryItem]
    total: int


class ImageStyleResponse(BaseModel):
    """사용 가능한 이미지 스타일 목록."""

    styles: list[str]
    provider: str
