import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.episode import Episode
from app.models.user import User
from app.models.webtoon import Webtoon
from app.schemas.webtoon import EpisodeDetail, WebtoonDetail, WebtoonListResponse

router = APIRouter()


def _allowed_ratings(user: User) -> list[str]:
    """사용자 연령 인증 상태에 따라 허용 등급 목록을 반환한다."""
    if user.adult_verified_at is not None:
        return ["all", "12+", "15+", "18+"]
    if user.age_group == "minor_safe":
        return ["all", "12+", "15+"]
    return ["all", "12+"]


@router.get("", response_model=WebtoonListResponse)
async def list_webtoons(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    platform: str | None = Query(None, pattern="^(naver|kakao|lezhin|ridibooks|toptoon)$"),
    genre: str | None = Query(None, max_length=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """웹툰 목록 조회. 연령등급 필터링 적용."""
    allowed = _allowed_ratings(user)
    base = select(Webtoon).where(Webtoon.age_rating.in_(allowed))

    if platform:
        base = base.where(Webtoon.platform == platform)
    if genre:
        base = base.where(Webtoon.genre.contains([genre]))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()

    result = await db.execute(base.order_by(Webtoon.created_at.desc()).offset(skip).limit(limit))
    items = result.scalars().all()
    return {"items": list(items), "total": total}


@router.get("/{webtoon_id}", response_model=WebtoonDetail)
async def get_webtoon(
    webtoon_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """웹툰 상세 + 회차 목록."""
    result = await db.execute(select(Webtoon).options(selectinload(Webtoon.episodes)).where(Webtoon.id == webtoon_id))
    webtoon = result.scalar_one_or_none()
    if webtoon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webtoon not found")

    # 연령등급 게이트
    allowed = _allowed_ratings(user)
    if webtoon.age_rating not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adult verification required",
        )

    # 회차를 episode_number 순으로 정렬
    webtoon.episodes.sort(key=lambda e: e.episode_number)
    return webtoon


@router.get("/{webtoon_id}/episodes/{episode_number}", response_model=EpisodeDetail)
async def get_episode(
    webtoon_id: uuid.UUID,
    episode_number: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회차 상세 (감정 분석 + 댓글 통계 포함)."""
    # 웹툰 연령등급 확인
    wt_result = await db.execute(select(Webtoon).where(Webtoon.id == webtoon_id))
    webtoon = wt_result.scalar_one_or_none()
    if webtoon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webtoon not found")

    allowed = _allowed_ratings(user)
    if webtoon.age_rating not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adult verification required",
        )

    result = await db.execute(
        select(Episode)
        .options(
            selectinload(Episode.emotions),
            selectinload(Episode.comment_stats),
        )
        .where(Episode.webtoon_id == webtoon_id, Episode.episode_number == episode_number)
    )
    episode = result.scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    return episode
