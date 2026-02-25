"""공개 화면 플래그 조회 API. 인증 불필요.

프론트엔드 라우트 게이트에서 로그인 전/후 모두 호출한다.
"""
from fastapi import APIRouter

from app.services.feature_flag_service import get_all_flags

router = APIRouter()


@router.get("")
async def get_feature_flags() -> dict[str, bool]:
    """모든 화면의 활성화 상태를 반환."""
    return await get_all_flags()
