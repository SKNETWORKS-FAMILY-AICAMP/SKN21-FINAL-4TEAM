import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lorebook_entry import LorebookEntry
from app.models.persona import Persona
from app.models.user import User

logger = logging.getLogger(__name__)


class CharacterCardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_persona(self, persona_id: uuid.UUID, user: User) -> dict:
        """Export persona to SillyTavern-compatible character card JSON."""
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        # Check access: owner, public, or admin
        if (
            persona.visibility == "private"
            and persona.created_by != user.id
            and user.role not in ("admin", "superadmin")
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Load lorebook
        lore_result = await self.db.execute(select(LorebookEntry).where(LorebookEntry.persona_id == persona_id))
        lorebook_entries = lore_result.scalars().all()

        # Build example dialogue string
        mes_example = ""
        if persona.example_dialogues:
            parts = []
            for dialogue in persona.example_dialogues:
                parts.append("<START>")
                if dialogue.get("user"):
                    parts.append(f"{{{{user}}}}: {dialogue['user']}")
                if dialogue.get("assistant"):
                    parts.append(f"{{{{char}}}}: {dialogue['assistant']}")
            mes_example = "\n".join(parts)

        card = {
            "name": persona.display_name or persona.persona_key,
            "description": persona.description or "",
            "personality": "",
            "first_mes": persona.greeting_message or "",
            "scenario": persona.scenario or "",
            "mes_example": mes_example,
            "tags": persona.tags or [],
            "system_prompt": persona.system_prompt,
            "extensions": {
                "webtoon_chatbot": {
                    "persona_key": persona.persona_key,
                    "version": persona.version,
                    "style_rules": persona.style_rules,
                    "safety_rules": persona.safety_rules,
                    "review_template": persona.review_template,
                    "catchphrases": persona.catchphrases or [],
                    "age_rating": persona.age_rating,
                    "lorebook": [
                        {"title": e.title, "content": e.content, "tags": e.tags or []} for e in lorebook_entries
                    ],
                }
            },
        }
        return card

    async def import_persona(self, card_data: dict, user: User) -> Persona:
        """Import a character card JSON into a new persona."""
        # Auto-detect format (SillyTavern vs Character.AI)
        name = card_data.get("name") or card_data.get("char_name") or "Imported Character"
        description = card_data.get("description") or card_data.get("char_persona") or ""
        system_prompt = card_data.get("system_prompt") or card_data.get("description") or description
        greeting = card_data.get("first_mes") or card_data.get("char_greeting") or None
        scenario = card_data.get("scenario") or None
        tags = card_data.get("tags") or []

        # Parse example dialogues from mes_example string
        example_dialogues = []
        mes_example = card_data.get("mes_example") or ""
        if mes_example:
            example_dialogues = self._parse_mes_example(mes_example)

        # Extract extensions (webtoon_chatbot specific)
        ext = card_data.get("extensions", {}).get("webtoon_chatbot", {})
        style_rules = ext.get("style_rules", {})
        safety_rules = ext.get("safety_rules", {})
        age_rating = ext.get("age_rating", "all")

        # Age rating check
        if age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required for 18+ personas",
            )

        # Ensure valid age_rating
        if age_rating not in ("all", "15+", "18+"):
            age_rating = "all"

        persona = Persona(
            created_by=user.id,
            type="user_created",
            visibility="private",
            moderation_status="pending",
            persona_key=f"imported_{uuid.uuid4().hex[:8]}",
            version="v1.0",
            display_name=name[:100],
            description=description[:2000] if description else None,
            system_prompt=system_prompt or "You are a character.",
            style_rules=style_rules or {},
            safety_rules=safety_rules or {},
            greeting_message=greeting,
            scenario=scenario,
            example_dialogues=example_dialogues or None,
            tags=tags[:10] if tags else None,
            age_rating=age_rating,
            is_active=True,
        )
        self.db.add(persona)
        await self.db.flush()

        # Import lorebook entries from extensions
        for entry_data in ext.get("lorebook", []):
            entry = LorebookEntry(
                persona_id=persona.id,
                created_by=user.id,
                title=entry_data.get("title", "Untitled"),
                content=entry_data.get("content", ""),
                tags=entry_data.get("tags"),
            )
            self.db.add(entry)

        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    @staticmethod
    def _parse_mes_example(mes_example: str) -> list[dict]:
        """Parse SillyTavern mes_example format into structured dialogues."""
        dialogues = []
        current = {}

        for line in mes_example.split("\n"):
            line = line.strip()
            if line == "<START>":
                if current:
                    dialogues.append(current)
                current = {}
            elif line.startswith("{{user}}:"):
                current["user"] = line[len("{{user}}:") :].strip()
            elif line.startswith("{{char}}:"):
                current["assistant"] = line[len("{{char}}:") :].strip()

        if current:
            dialogues.append(current)

        return dialogues
