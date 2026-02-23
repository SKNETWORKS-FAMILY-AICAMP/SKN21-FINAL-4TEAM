import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.favorite import FavoriteResponse
from app.services.favorite_service import FavoriteService

router = APIRouter()


@router.get("")
async def list_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FavoriteService(db)
    return await svc.list_by_user(user.id, skip=skip, limit=limit)


@router.post("/{persona_id}", response_model=FavoriteResponse, status_code=201)
async def add_favorite(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FavoriteService(db)
    return await svc.add(user.id, persona_id)


@router.delete("/{persona_id}", status_code=204)
async def remove_favorite(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = FavoriteService(db)
    await svc.remove(user.id, persona_id)
