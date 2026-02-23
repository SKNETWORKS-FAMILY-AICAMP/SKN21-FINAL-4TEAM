import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.relationship import RelationshipResponse
from app.services.relationship_service import RelationshipService

router = APIRouter()


@router.get("/", response_model=list[RelationshipResponse])
async def list_relationships(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RelationshipService(db)
    return await svc.list_by_user(user.id)


@router.get("/{persona_id}", response_model=RelationshipResponse)
async def get_relationship(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RelationshipService(db)
    rel = await svc.get(user.id, persona_id)
    if rel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    return rel
