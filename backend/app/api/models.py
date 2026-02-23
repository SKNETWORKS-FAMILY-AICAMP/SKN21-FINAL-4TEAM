import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.llm_model import LLMModel
from app.models.user import User
from app.schemas.llm_model import LLMModelResponse

router = APIRouter()


class PreferredModelRequest(BaseModel):
    model_id: uuid.UUID


@router.get("", response_model=list[LLMModelResponse])
async def list_available_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용 가능한 LLM 모델 목록. 활성 모델만, 성인전용 모델은 성인인증 사용자에게만 노출."""
    query = select(LLMModel).where(LLMModel.is_active.is_(True))

    if user.adult_verified_at is None:
        query = query.where(LLMModel.is_adult_only.is_(False))

    result = await db.execute(query.order_by(LLMModel.display_name))
    return list(result.scalars().all())


@router.put("/preferred", response_model=LLMModelResponse)
async def set_preferred_model(
    data: PreferredModelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """선호 LLM 모델 변경."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == data.model_id))
    model = result.scalar_one_or_none()

    if model is None or not model.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or inactive",
        )

    # 성인전용 모델은 성인인증 필요
    if model.is_adult_only and user.adult_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adult verification required for this model",
        )

    user.preferred_llm_model_id = model.id
    await db.commit()
    return model
