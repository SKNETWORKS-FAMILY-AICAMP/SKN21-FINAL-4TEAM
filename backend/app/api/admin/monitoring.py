from fastapi import APIRouter, Depends

from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_system_stats(admin: User = Depends(require_admin)):
    """시스템 통계 (세션수, 메시지수, 활성 사용자)."""
    raise NotImplementedError


@router.get("/logs")
async def get_policy_violation_logs(admin: User = Depends(require_admin)):
    """정책 위반 로그 조회."""
    raise NotImplementedError
