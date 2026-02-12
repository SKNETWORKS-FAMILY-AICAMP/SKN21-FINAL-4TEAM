from fastapi import APIRouter, Depends

from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/config")
async def get_system_config(admin: User = Depends(require_admin)):
    """시스템 설정 조회 (RunPod 엔드포인트, 캐시 등)."""
    raise NotImplementedError


@router.put("/config")
async def update_system_config(admin: User = Depends(require_admin)):
    """시스템 설정 변경."""
    raise NotImplementedError
