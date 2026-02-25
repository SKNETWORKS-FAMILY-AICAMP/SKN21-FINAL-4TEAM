import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.relationship import RelationshipWithPersonaResponse
from app.services.relationship_service import RelationshipService

router = APIRouter()


@router.get("/", response_model=list[RelationshipWithPersonaResponse])
async def list_relationships(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RelationshipService(db)
    return await svc.list_by_user(user.id)


@router.get("/{persona_id}")
async def get_relationship(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RelationshipService(db)
    rel = await svc.get(user.id, persona_id)
    if rel is None:
        # 아직 대화 이력 없음 → 기본 stranger 상태 반환 (404 대신 200)
        return {
            "user_id": str(user.id),
            "persona_id": str(persona_id),
            "affection_level": 0,
            "relationship_stage": "stranger",
            "interaction_count": 0,
        }
    return rel
