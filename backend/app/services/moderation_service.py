import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona


class ModerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_moderation_queue(self, moderation_status: str = "pending", skip: int = 0, limit: int = 20) -> dict:
        """모더레이션 대기열 조회."""
        count_query = select(func.count()).select_from(Persona).where(Persona.moderation_status == moderation_status)
        total = (await self.db.execute(count_query)).scalar()

        query = (
            select(Persona)
            .where(Persona.moderation_status == moderation_status)
            .order_by(Persona.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def review_persona(self, persona_id: uuid.UUID, action: str) -> Persona:
        """관리자 페르소나 모더레이션 (approve/block)."""
        if action not in ("approved", "blocked"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Action must be 'approved' or 'blocked'",
            )

        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        persona.moderation_status = action
        if action == "approved":
            persona.is_active = True
        elif action == "blocked":
            persona.is_active = False
        persona.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(persona)
        return persona
