"""관리자 세계관 이벤트 (大前提) API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.world_event import (
    WorldEventCreate,
    WorldEventListResponse,
    WorldEventResponse,
    WorldEventUpdate,
)
from app.services.world_event_service import WorldEventService

router = APIRouter()


@router.post("/", response_model=WorldEventResponse, status_code=201)
async def create_world_event(
    body: WorldEventCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """세계관 이벤트 생성."""
    svc = WorldEventService(db)
    event = await svc.create(
        admin_id=user.id,
        title=body.title,
        content=body.content,
        event_type=body.event_type,
        priority=body.priority,
        starts_at=body.starts_at,
        expires_at=body.expires_at,
        age_rating=body.age_rating,
    )
    return event


@router.get("/", response_model=WorldEventListResponse)
async def list_world_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 세계관 이벤트 목록 (관리자)."""
    svc = WorldEventService(db)
    return await svc.list_all(skip=skip, limit=limit)


@router.put("/{event_id}", response_model=WorldEventResponse)
async def update_world_event(
    event_id: uuid.UUID,
    body: WorldEventUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """세계관 이벤트 수정."""
    svc = WorldEventService(db)
    event = await svc.update(event_id, **body.model_dump(exclude_unset=True))
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.delete("/{event_id}", status_code=204)
async def delete_world_event(
    event_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """세계관 이벤트 삭제."""
    svc = WorldEventService(db)
    deleted = await svc.delete(event_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
