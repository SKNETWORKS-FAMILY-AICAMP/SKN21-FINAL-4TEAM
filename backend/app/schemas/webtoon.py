from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class EpisodeEmotionResponse(BaseModel):
    emotion_label: str
    intensity: float
    confidence: float

    model_config = {"from_attributes": True}


class CommentStatResponse(BaseModel):
    total_count: int
    positive_ratio: float | None
    negative_ratio: float | None
    top_emotions: dict | None
    toxicity_score: float | None
    collected_at: datetime

    model_config = {"from_attributes": True}


class EpisodeBrief(BaseModel):
    id: UUID
    episode_number: int
    title: str | None
    published_at: date | None

    model_config = {"from_attributes": True}


class EpisodeDetail(BaseModel):
    id: UUID
    webtoon_id: UUID
    episode_number: int
    title: str | None
    summary: str | None
    published_at: date | None
    created_at: datetime
    emotions: list[EpisodeEmotionResponse] = []
    comment_stats: list[CommentStatResponse] = []

    model_config = {"from_attributes": True}


class WebtoonResponse(BaseModel):
    id: UUID
    title: str
    platform: str | None
    genre: list[str] | None
    age_rating: str
    total_episodes: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebtoonDetail(WebtoonResponse):
    episodes: list[EpisodeBrief] = []


class WebtoonListResponse(BaseModel):
    items: list[WebtoonResponse]
    total: int
