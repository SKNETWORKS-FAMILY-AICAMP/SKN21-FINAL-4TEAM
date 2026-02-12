import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.episode import Episode
from app.models.live2d_model import Live2DModel
from app.models.user import User
from app.models.webtoon import Webtoon

router = APIRouter()


# ── Schemas ──


class WebtoonCreate(BaseModel):
    title: str
    platform: str | None = None
    genre: list[str] | None = None
    age_rating: str = "all"
    status: str = "ongoing"


class WebtoonResponse(BaseModel):
    id: uuid.UUID
    title: str
    platform: str | None
    genre: list[str] | None
    age_rating: str
    total_episodes: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebtoonListResponse(BaseModel):
    items: list[WebtoonResponse]
    total: int


class EpisodeCreate(BaseModel):
    episode_number: int
    title: str | None = None
    summary: str | None = None
    published_at: date | None = None


class EpisodeResponse(BaseModel):
    id: uuid.UUID
    webtoon_id: uuid.UUID
    episode_number: int
    title: str | None
    summary: str | None
    published_at: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Live2DModelCreate(BaseModel):
    name: str
    model_path: str
    thumbnail_url: str | None = None
    emotion_mappings: dict


class Live2DModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_path: str
    thumbnail_url: str | None
    emotion_mappings: dict
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Webtoon ──


@router.get("/webtoons", response_model=WebtoonListResponse)
async def list_webtoons(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """웹툰 목록."""
    total = (await db.execute(select(func.count()).select_from(Webtoon))).scalar()
    result = await db.execute(
        select(Webtoon).order_by(Webtoon.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return {"items": list(items), "total": total}


@router.post("/webtoons", response_model=WebtoonResponse, status_code=status.HTTP_201_CREATED)
async def create_webtoon(
    data: WebtoonCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """웹툰 등록."""
    webtoon = Webtoon(
        title=data.title,
        platform=data.platform,
        genre=data.genre,
        age_rating=data.age_rating,
        status=data.status,
    )
    db.add(webtoon)
    await db.commit()
    await db.refresh(webtoon)
    return webtoon


# ── Episode ──


@router.post("/webtoons/{webtoon_id}/episodes", response_model=EpisodeResponse, status_code=status.HTTP_201_CREATED)
async def create_episode(
    webtoon_id: uuid.UUID,
    data: EpisodeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """회차 등록."""
    # 웹툰 존재 확인
    result = await db.execute(select(Webtoon).where(Webtoon.id == webtoon_id))
    webtoon = result.scalar_one_or_none()
    if webtoon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webtoon not found")

    episode = Episode(
        webtoon_id=webtoon_id,
        episode_number=data.episode_number,
        title=data.title,
        summary=data.summary,
        published_at=data.published_at,
    )
    db.add(episode)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Episode number already exists for this webtoon",
        )

    # total_episodes 갱신
    webtoon.total_episodes = (
        await db.execute(
            select(func.count()).select_from(Episode).where(Episode.webtoon_id == webtoon_id)
        )
    ).scalar()
    webtoon.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(episode)
    return episode


# ── Live2D ──


@router.post("/live2d-models", response_model=Live2DModelResponse, status_code=status.HTTP_201_CREATED)
async def upload_live2d_model(
    data: Live2DModelCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Live2D 모델 에셋 등록."""
    model = Live2DModel(
        name=data.name,
        model_path=data.model_path,
        thumbnail_url=data.thumbnail_url,
        emotion_mappings=data.emotion_mappings,
        created_by=admin.id,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model
