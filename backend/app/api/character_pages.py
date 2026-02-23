"""캐릭터 페이지 API — 인스타그램 스타일 프로필, 팔로우, 게시물 피드."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.character_page import (
    CharacterPageResponse,
    FollowResponse,
    FollowerListResponse,
)
from app.services.character_page_service import CharacterPageService

router = APIRouter()


@router.get("/{persona_id}", response_model=CharacterPageResponse)
async def get_character_page(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캐릭터 프로필 페이지 조회."""
    svc = CharacterPageService(db)
    return await svc.get_character_page(persona_id, viewer=user)


@router.get("/{persona_id}/posts", response_model=dict)
async def get_character_posts(
    persona_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캐릭터 게시물 피드."""
    svc = CharacterPageService(db)
    return await svc.get_posts(persona_id, viewer=user, skip=skip, limit=limit)


@router.get("/{persona_id}/followers", response_model=FollowerListResponse)
async def get_followers(
    persona_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팔로워 목록."""
    svc = CharacterPageService(db)
    return await svc.get_followers(persona_id, viewer=user, skip=skip, limit=limit)


@router.post("/{persona_id}/follow", response_model=FollowResponse)
async def follow_character(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캐릭터 팔로우."""
    svc = CharacterPageService(db)
    return await svc.follow(user.id, persona_id)


@router.delete("/{persona_id}/follow", response_model=FollowResponse)
async def unfollow_character(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """캐릭터 언팔로우."""
    svc = CharacterPageService(db)
    return await svc.unfollow(user.id, persona_id)
