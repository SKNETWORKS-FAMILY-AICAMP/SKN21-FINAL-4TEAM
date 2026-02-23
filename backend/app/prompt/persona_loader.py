import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lorebook_entry import LorebookEntry
from app.models.persona import Persona


class PersonaLoader:
    """페르소나 데이터를 프롬프트 형식으로 변환."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, persona_id: uuid.UUID) -> dict:
        """페르소나 + 관련 로어북 로드."""
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise ValueError(f"Persona {persona_id} not found")

        # 로어북 항목 로드
        lore_result = await self.db.execute(
            select(LorebookEntry).where(LorebookEntry.persona_id == persona_id).order_by(LorebookEntry.created_at.asc())
        )
        lorebook_entries = lore_result.scalars().all()

        return {
            "persona_key": persona.persona_key,
            "display_name": persona.display_name or persona.persona_key,
            "description": persona.description,
            "system_prompt": persona.system_prompt,
            "style_rules": persona.style_rules,
            "safety_rules": persona.safety_rules,
            "review_template": persona.review_template,
            "catchphrases": persona.catchphrases or [],
            "greeting_message": persona.greeting_message,
            "scenario": persona.scenario,
            "example_dialogues": persona.example_dialogues or [],
            "tags": persona.tags or [],
            "age_rating": persona.age_rating,
            "lorebook": [{"title": e.title, "content": e.content, "tags": e.tags or []} for e in lorebook_entries],
        }
