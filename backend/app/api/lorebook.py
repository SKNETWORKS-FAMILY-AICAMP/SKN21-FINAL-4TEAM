from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/persona/{persona_id}")
async def list_persona_lorebook(
    persona_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 로어북 항목 목록."""
    raise NotImplementedError


@router.post("/")
async def create_lorebook_entry(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로어북 항목 생성."""
    raise NotImplementedError


@router.put("/{entry_id}")
async def update_lorebook_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로어북 항목 수정 (소유자만)."""
    raise NotImplementedError


@router.delete("/{entry_id}")
async def delete_lorebook_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로어북 항목 삭제 (소유자만)."""
    raise NotImplementedError
