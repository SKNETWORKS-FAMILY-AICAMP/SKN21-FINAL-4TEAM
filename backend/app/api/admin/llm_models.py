import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.llm_model import LLMModel
from app.models.user import User
from app.schemas.llm_model import LLMModelCreate, LLMModelResponse, LLMModelUpdate

router = APIRouter()


class LLMModelListResponse(BaseModel):
    items: list[LLMModelResponse]
    total: int


@router.get("/", response_model=LLMModelListResponse)
async def list_all_models(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 LLM 모델 목록 (비활성 포함)."""
    total = (await db.execute(select(func.count()).select_from(LLMModel))).scalar()
    result = await db.execute(
        select(LLMModel).order_by(LLMModel.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return {"items": list(items), "total": total}


@router.post("/", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def register_model(
    data: LLMModelCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """LLM 모델 등록."""
    model = LLMModel(
        provider=data.provider,
        model_id=data.model_id,
        display_name=data.display_name,
        input_cost_per_1m=data.input_cost_per_1m,
        output_cost_per_1m=data.output_cost_per_1m,
        max_context_length=data.max_context_length,
        is_adult_only=data.is_adult_only,
        metadata_=data.metadata,
    )
    db.add(model)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model with same provider + model_id already exists",
        )
    await db.refresh(model)
    return model


@router.put("/{model_id}", response_model=LLMModelResponse)
async def update_model(
    model_id: uuid.UUID,
    data: LLMModelUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """LLM 모델 정보/비용 수정."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    update_data = data.model_dump(exclude_unset=True)
    # metadata 필드명 매핑
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")
    for field, value in update_data.items():
        setattr(model, field, value)

    await db.commit()
    await db.refresh(model)
    return model


@router.put("/{model_id}/toggle", response_model=LLMModelResponse)
async def toggle_model_active(
    model_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """LLM 모델 활성/비활성 전환."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    model.is_active = not model.is_active
    await db.commit()
    await db.refresh(model)
    return model
