from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/")
async def list_all_models(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 LLM 모델 목록 (비활성 포함)."""
    raise NotImplementedError


@router.post("/")
async def register_model(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """LLM 모델 등록."""
    raise NotImplementedError


@router.put("/{model_id}")
async def update_model(
    model_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """LLM 모델 정보/비용 수정."""
    raise NotImplementedError


@router.put("/{model_id}/toggle")
async def toggle_model_active(
    model_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """LLM 모델 활성/비활성 전환."""
    raise NotImplementedError
