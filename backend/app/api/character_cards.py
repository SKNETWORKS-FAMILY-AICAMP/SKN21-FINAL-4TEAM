import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.persona import PersonaResponse
from app.services.character_card_service import CharacterCardService

router = APIRouter()


@router.get("/export/{persona_id}")
async def export_character_card(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CharacterCardService(db)
    return await svc.export_persona(persona_id, user)


@router.post("/import", response_model=PersonaResponse, status_code=201)
async def import_character_card(
    card_data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = CharacterCardService(db)
    return await svc.import_persona(card_data, user)
