import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona_relationship import PersonaRelationship

# Affection thresholds for stage transitions
STAGE_THRESHOLDS = [
    (0, "stranger"),
    (100, "acquaintance"),
    (250, "friend"),
    (450, "close_friend"),
    (650, "crush"),
    (800, "lover"),
    (950, "soulmate"),
]


class RelationshipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> PersonaRelationship:
        result = await self.db.execute(
            select(PersonaRelationship).where(
                PersonaRelationship.user_id == user_id,
                PersonaRelationship.persona_id == persona_id,
            )
        )
        rel = result.scalar_one_or_none()
        if rel is None:
            rel = PersonaRelationship(user_id=user_id, persona_id=persona_id)
            self.db.add(rel)
            await self.db.flush()
        return rel

    async def get(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> PersonaRelationship | None:
        result = await self.db.execute(
            select(PersonaRelationship).where(
                PersonaRelationship.user_id == user_id,
                PersonaRelationship.persona_id == persona_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[PersonaRelationship]:
        result = await self.db.execute(
            select(PersonaRelationship)
            .where(PersonaRelationship.user_id == user_id)
            .order_by(PersonaRelationship.affection_level.desc())
        )
        return list(result.scalars().all())

    async def update_after_interaction(
        self,
        user_id: uuid.UUID,
        persona_id: uuid.UUID,
        emotion_signal: dict | None = None,
    ) -> tuple[PersonaRelationship, bool]:
        """Update relationship after a chat interaction. Returns (relationship, stage_changed)."""
        rel = await self.get_or_create(user_id, persona_id)
        old_stage = rel.relationship_stage

        # Increment interaction count
        rel.interaction_count += 1
        rel.last_interaction_at = datetime.now(UTC)

        # Calculate affection delta based on emotion signal
        delta = self._calculate_affection_delta(emotion_signal)
        rel.affection_level = max(0, min(1000, rel.affection_level + delta))

        # Update stage based on new affection level
        rel.relationship_stage = self._determine_stage(rel.affection_level)
        rel.updated_at = datetime.now(UTC)

        stage_changed = old_stage != rel.relationship_stage
        return rel, stage_changed

    @staticmethod
    def _calculate_affection_delta(emotion_signal: dict | None) -> int:
        if not emotion_signal:
            return 2  # Default small positive for any interaction

        dominant = emotion_signal.get("label", "")
        positive_emotions = {"기쁨", "사랑", "감동", "설렘", "감사", "행복", "흥미", "즐거움"}
        negative_emotions = {"분노", "슬픔", "혐오", "공포", "실망", "짜증"}

        if dominant in positive_emotions:
            return 4
        elif dominant in negative_emotions:
            return -2
        return 2

    @staticmethod
    def _determine_stage(affection_level: int) -> str:
        stage = "stranger"
        for threshold, name in STAGE_THRESHOLDS:
            if affection_level >= threshold:
                stage = name
        return stage
