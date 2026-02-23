import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.user_memory import UserMemory

router = APIRouter()


class MemoryCreate(BaseModel):
    memory_type: str = Field(default="manual", max_length=20)
    namespace: str = Field(default="general", max_length=50)
    key: str = Field(..., min_length=1, max_length=200)
    value: dict


class MemoryResponse(BaseModel):
    id: uuid.UUID
    memory_type: str
    namespace: str
    key: str
    value: dict
    created_at: str

    model_config = {"from_attributes": True}


@router.get("")
async def list_memories(
    namespace: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [UserMemory.user_id == user.id]
    if namespace:
        filters.append(UserMemory.namespace == namespace)

    count_query = select(func.count()).select_from(UserMemory).where(*filters)
    total = (await db.execute(count_query)).scalar()

    query = select(UserMemory).where(*filters).order_by(UserMemory.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": list(items), "total": total}


@router.post("/", status_code=201)
async def create_memory(
    data: MemoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memory = UserMemory(
        user_id=user.id,
        memory_type=data.memory_type,
        namespace=data.namespace,
        key=data.key,
        value=data.value,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserMemory).where(UserMemory.id == memory_id, UserMemory.user_id == user.id))
    memory = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.delete(memory)
    await db.commit()
