from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/")
async def list_personas_for_moderation(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """모더레이션 대기 페르소나 목록."""
    raise NotImplementedError


@router.put("/{persona_id}/moderation")
async def update_moderation_status(
    persona_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 모더레이션 상태 변경 (approve/block)."""
    raise NotImplementedError
