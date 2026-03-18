"""커뮤니티 피드 API 라우터."""

import logging
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token, is_token_blacklisted
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.community import CommunityPostListResponse, CommunityPostResponse, LikeToggleResponse
from app.services.community_service import CommunityService

logger = logging.getLogger(__name__)

router = APIRouter()

# auto_error=False: Authorization 헤더 없어도 에러 미발생
_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """선택적 인증 의존성. 토큰이 없으면 None 반환, 있으면 검증 후 User 반환."""
    token = credentials.credentials if credentials else access_token
    if not token:
        return None

    payload = decode_access_token(token)
    if payload is None:
        return None

    if await is_token_blacklisted(token):
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


@router.get("/feed", response_model=CommunityPostListResponse)
async def get_community_feed(
    tab: str = Query("all", description="all | following"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> CommunityPostListResponse:
    """커뮤니티 피드 조회. 비로그인 시 is_liked=False, following 탭은 빈 결과."""
    svc = CommunityService(db)
    items, total = await svc.get_feed(
        user_id=current_user.id if current_user else None,
        tab=tab,
        offset=offset,
        limit=limit,
    )
    return CommunityPostListResponse(
        items=[CommunityPostResponse(**item) for item in items],
        total=total,
        has_more=(offset + limit) < total,
    )


@router.post("/{post_id}/like", response_model=LikeToggleResponse)
async def toggle_post_like(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeToggleResponse:
    """포스트 좋아요 토글. 인증 필수."""
    svc = CommunityService(db)
    try:
        return await svc.toggle_like(current_user.id, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
