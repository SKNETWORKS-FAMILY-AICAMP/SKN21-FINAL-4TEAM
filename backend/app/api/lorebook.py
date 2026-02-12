import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.lorebook import LorebookCreate, LorebookListResponse, LorebookResponse, LorebookUpdate
from app.services.lorebook_service import LorebookService

router = APIRouter()


@router.get("/persona/{persona_id}", response_model=LorebookListResponse)
async def list_persona_lorebook(
    persona_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 로어북 항목 목록."""
    service = LorebookService(db)
    return await service.list_by_persona(persona_id, skip=skip, limit=limit)


@router.post("/", response_model=LorebookResponse, status_code=status.HTTP_201_CREATED)
async def create_lorebook_entry(
    data: LorebookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로어북 항목 생성."""
    service = LorebookService(db)
    return await service.create_entry(data, user)


@router.put("/{entry_id}", response_model=LorebookResponse)
async def update_lorebook_entry(
    entry_id: int,
    data: LorebookUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로어북 항목 수정 (소유자만)."""
    service = LorebookService(db)
    return await service.update_entry(entry_id, data, user)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lorebook_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로어북 항목 삭제 (소유자만)."""
    service = LorebookService(db)
    await service.delete_entry(entry_id, user)
