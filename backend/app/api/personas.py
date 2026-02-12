from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/")
async def list_personas(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 목록 조회 (공개 + 내 페르소나)."""
    raise NotImplementedError


@router.post("/")
async def create_persona(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 생성."""
    raise NotImplementedError


@router.get("/{persona_id}")
async def get_persona(
    persona_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 상세 조회."""
    raise NotImplementedError


@router.put("/{persona_id}")
async def update_persona(
    persona_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 수정 (소유자만)."""
    raise NotImplementedError


@router.delete("/{persona_id}")
async def delete_persona(
    persona_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 삭제 (소유자만)."""
    raise NotImplementedError
