import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.persona import PersonaCreate, PersonaListResponse, PersonaResponse, PersonaUpdate
from app.services.persona_service import PersonaService

router = APIRouter()


@router.get("/", response_model=PersonaListResponse)
async def list_personas(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 목록 조회 (공개 + 내 페르소나)."""
    service = PersonaService(db)
    return await service.list_personas(user, skip=skip, limit=limit)


@router.post("/", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    data: PersonaCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 생성."""
    service = PersonaService(db)
    try:
        return await service.create_persona(data, user)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persona key + version already exists",
        )


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 상세 조회."""
    service = PersonaService(db)
    return await service.get_persona(persona_id, user)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: uuid.UUID,
    data: PersonaUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 수정 (소유자만)."""
    service = PersonaService(db)
    return await service.update_persona(persona_id, data, user)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 삭제 (소유자만)."""
    service = PersonaService(db)
    await service.delete_persona(persona_id, user)
