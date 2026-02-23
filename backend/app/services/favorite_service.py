import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.persona_favorite import PersonaFavorite


class FavoriteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> PersonaFavorite:
        # Check persona exists
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        # Check if already favorited
        existing = await self.db.execute(
            select(PersonaFavorite).where(
                PersonaFavorite.user_id == user_id,
                PersonaFavorite.persona_id == persona_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already favorited")

        fav = PersonaFavorite(user_id=user_id, persona_id=persona_id)
        self.db.add(fav)

        # Increment like_count
        persona.like_count = persona.like_count + 1

        await self.db.commit()
        await self.db.refresh(fav)
        return fav

    async def remove(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(PersonaFavorite).where(
                PersonaFavorite.user_id == user_id,
                PersonaFavorite.persona_id == persona_id,
            )
        )
        fav = result.scalar_one_or_none()
        if fav is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

        # Decrement like_count
        persona_result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = persona_result.scalar_one_or_none()
        if persona and persona.like_count > 0:
            persona.like_count = persona.like_count - 1

        await self.db.delete(fav)
        await self.db.commit()

    async def list_by_user(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> dict:
        count_query = select(func.count()).select_from(PersonaFavorite).where(PersonaFavorite.user_id == user_id)
        total = (await self.db.execute(count_query)).scalar()

        query = (
            select(
                PersonaFavorite.id,
                PersonaFavorite.persona_id,
                PersonaFavorite.created_at,
                Persona.display_name.label("persona_display_name"),
                Persona.description.label("persona_description"),
                Persona.age_rating.label("persona_age_rating"),
                Persona.background_image_url.label("persona_background_image_url"),
                Persona.chat_count.label("persona_chat_count"),
                Persona.like_count.label("persona_like_count"),
                Persona.tags.label("persona_tags"),
                Persona.category.label("persona_category"),
            )
            .join(Persona, PersonaFavorite.persona_id == Persona.id)
            .where(PersonaFavorite.user_id == user_id)
            .order_by(PersonaFavorite.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        rows = result.all()
        items = [
            {
                "id": str(row.id),
                "persona_id": str(row.persona_id),
                "created_at": row.created_at.isoformat(),
                "persona_display_name": row.persona_display_name,
                "persona_description": row.persona_description,
                "persona_age_rating": row.persona_age_rating,
                "persona_background_image_url": row.persona_background_image_url,
                "persona_chat_count": row.persona_chat_count,
                "persona_like_count": row.persona_like_count,
                "persona_tags": row.persona_tags,
                "persona_category": row.persona_category,
            }
            for row in rows
        ]
        return {"items": items, "total": total}

    async def is_favorited(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(PersonaFavorite).where(
                PersonaFavorite.user_id == user_id,
                PersonaFavorite.persona_id == persona_id,
            )
        )
        return result.scalar_one_or_none() is not None
