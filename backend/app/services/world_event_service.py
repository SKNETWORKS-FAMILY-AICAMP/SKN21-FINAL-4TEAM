"""세계관 이벤트 (大前提) 서비스.

관리자가 세계 상황을 생성/관리하고, 모든 캐릭터 프롬프트에 주입되는 이벤트를 제공한다.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.world_event import WorldEvent


class WorldEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        admin_id: uuid.UUID,
        title: str,
        content: str,
        event_type: str = "world_state",
        priority: int = 0,
        starts_at: datetime | None = None,
        expires_at: datetime | None = None,
        age_rating: str = "all",
    ) -> WorldEvent:
        event = WorldEvent(
            created_by=admin_id,
            title=title,
            content=content,
            event_type=event_type,
            priority=priority,
            starts_at=starts_at,
            expires_at=expires_at,
            age_rating=age_rating,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get(self, event_id: uuid.UUID) -> WorldEvent | None:
        result = await self.db.execute(select(WorldEvent).where(WorldEvent.id == event_id))
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 50) -> dict:
        total = (await self.db.execute(select(func.count()).select_from(WorldEvent))).scalar()
        q = select(WorldEvent).order_by(WorldEvent.priority.desc(), WorldEvent.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        items = list(result.scalars().all())
        return {"items": items, "total": total}

    _UPDATABLE_FIELDS = frozenset({
        "title", "content", "event_type", "priority",
        "is_active", "starts_at", "expires_at", "age_rating",
    })

    async def update(self, event_id: uuid.UUID, **kwargs) -> WorldEvent | None:
        event = await self.get(event_id)
        if event is None:
            return None

        for key, value in kwargs.items():
            if value is not None and key in self._UPDATABLE_FIELDS:
                setattr(event, key, value)

        event.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def delete(self, event_id: uuid.UUID) -> bool:
        event = await self.get(event_id)
        if event is None:
            return False
        await self.db.delete(event)
        await self.db.commit()
        return True

    async def get_active_events(self, age_rating_filter: str = "all") -> list[WorldEvent]:
        """현재 활성 이벤트 조회. starts_at/expires_at 범위 체크 포함."""
        now = datetime.now(UTC)

        q = select(WorldEvent).where(WorldEvent.is_active == True)

        # 시간 범위 필터: starts_at이 null이거나 현재 이후
        q = q.where(
            (WorldEvent.starts_at == None) | (WorldEvent.starts_at <= now)  # noqa: E711
        )
        q = q.where(
            (WorldEvent.expires_at == None) | (WorldEvent.expires_at > now)  # noqa: E711
        )

        # 연령등급 필터: 해당 등급 이하만
        age_levels = {"all": ["all"], "15+": ["all", "15+"], "18+": ["all", "15+", "18+"]}
        allowed = age_levels.get(age_rating_filter, ["all"])
        q = q.where(WorldEvent.age_rating.in_(allowed))

        q = q.order_by(WorldEvent.priority.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    def format_for_prompt(self, events: list[WorldEvent]) -> str:
        """세계관 이벤트를 프롬프트 주입용 텍스트로 포맷."""
        if not events:
            return ""

        parts = ["[World State — 大前提: 현재 세계 상황]"]
        for event in events:
            parts.append(f"- [{event.event_type}] {event.title}: {event.content}")
        return "\n".join(parts)
