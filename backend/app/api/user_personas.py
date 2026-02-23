import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user_persona import UserPersonaCreate, UserPersonaResponse, UserPersonaUpdate
from app.services.user_persona_service import UserPersonaService

router = APIRouter()


@router.get("", response_model=list[UserPersonaResponse])
async def list_user_personas(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserPersonaService(db)
    return await svc.list_by_user(user.id)


@router.post("", response_model=UserPersonaResponse, status_code=201)
async def create_user_persona(
    data: UserPersonaCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserPersonaService(db)
    return await svc.create(
        user.id,
        display_name=data.display_name,
        description=data.description,
        avatar_url=data.avatar_url,
    )


@router.patch("/{persona_id}", response_model=UserPersonaResponse)
async def update_user_persona(
    persona_id: uuid.UUID,
    data: UserPersonaUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserPersonaService(db)
    update_data = data.model_dump(exclude_unset=True)
    return await svc.update(persona_id, user.id, **update_data)


@router.delete("/{persona_id}", status_code=204)
async def delete_user_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserPersonaService(db)
    await svc.delete(persona_id, user.id)


@router.post("/{persona_id}/set-default", response_model=UserPersonaResponse)
async def set_default_user_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = UserPersonaService(db)
    return await svc.set_default(persona_id, user.id)
