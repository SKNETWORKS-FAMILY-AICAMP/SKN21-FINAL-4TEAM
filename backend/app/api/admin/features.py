"""관리자 화면 활성화/비활성화 관리 API."""
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import require_admin, require_superadmin
from app.models.user import User
from app.services.feature_flag_service import (
    ALL_SCREENS,
    get_all_flags,
    reset_all_flags,
    set_flag,
)

router = APIRouter()


class ScreenFlagResponse(BaseModel):
    key: str
    label: str
    description: str
    category: str
    enabled: bool


class FlagUpdateRequest(BaseModel):
    enabled: bool


@router.get("", response_model=list[ScreenFlagResponse])
async def list_feature_flags(admin: User = Depends(require_admin)) -> list[ScreenFlagResponse]:
    """모든 화면 플래그 목록 및 현재 상태 조회."""
    flags = await get_all_flags()
    return [
        ScreenFlagResponse(
            key=m.key,
            label=m.label,
            description=m.description,
            category=m.category,
            enabled=flags.get(m.key, True),
        )
        for m in ALL_SCREENS
    ]


@router.patch("/{key}", response_model=ScreenFlagResponse)
async def update_feature_flag(
    key: str,
    body: FlagUpdateRequest = Body(...),
    admin: User = Depends(require_superadmin),
) -> ScreenFlagResponse:
    """화면 플래그 활성화/비활성화. superadmin만 가능."""
    meta = next((m for m in ALL_SCREENS if m.key == key), None)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{key}' not found",
        )
    await set_flag(key, body.enabled)
    return ScreenFlagResponse(
        key=meta.key,
        label=meta.label,
        description=meta.description,
        category=meta.category,
        enabled=body.enabled,
    )


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset_feature_flags(admin: User = Depends(require_superadmin)) -> dict:
    """모든 화면 플래그를 기본값(전체 활성화)으로 초기화."""
    await reset_all_flags()
    return {"message": "모든 화면 플래그가 초기화되었습니다."}
