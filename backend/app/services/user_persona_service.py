import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_persona import UserPersona


class UserPersonaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user(self, user_id: uuid.UUID) -> list[UserPersona]:
        result = await self.db.execute(
            select(UserPersona).where(UserPersona.user_id == user_id).order_by(UserPersona.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        user_id: uuid.UUID,
        display_name: str,
        description: str | None = None,
        avatar_url: str | None = None,
    ) -> UserPersona:
        persona = UserPersona(
            user_id=user_id,
            display_name=display_name,
            description=description,
            avatar_url=avatar_url,
        )
        self.db.add(persona)
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def update(self, persona_id: uuid.UUID, user_id: uuid.UUID, **kwargs) -> UserPersona:
        persona = await self._get_or_404(persona_id, user_id)
        for key, value in kwargs.items():
            if value is not None:
                setattr(persona, key, value)
        persona.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def delete(self, persona_id: uuid.UUID, user_id: uuid.UUID) -> None:
        persona = await self._get_or_404(persona_id, user_id)
        await self.db.delete(persona)
        await self.db.commit()

    async def set_default(self, persona_id: uuid.UUID, user_id: uuid.UUID) -> UserPersona:
        # Clear existing defaults
        result = await self.db.execute(
            select(UserPersona).where(UserPersona.user_id == user_id, UserPersona.is_default == True)
        )
        for p in result.scalars().all():
            p.is_default = False

        persona = await self._get_or_404(persona_id, user_id)
        persona.is_default = True
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def _get_or_404(self, persona_id: uuid.UUID, user_id: uuid.UUID) -> UserPersona:
        result = await self.db.execute(
            select(UserPersona).where(UserPersona.id == persona_id, UserPersona.user_id == user_id)
        )
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User persona not found")
        return persona
