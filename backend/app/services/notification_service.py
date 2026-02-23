import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        type_: str,
        title: str,
        body: str | None = None,
        link: str | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            body=body,
            link=link,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        is_read: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        filters = [Notification.user_id == user_id]
        if is_read is not None:
            filters.append(Notification.is_read == is_read)

        count_query = select(func.count()).select_from(Notification).where(*filters)
        total = (await self.db.execute(count_query)).scalar()

        query = select(Notification).where(*filters).order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def unread_count(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
        return result.scalar() or 0

    async def mark_as_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        notification = result.scalar_one_or_none()
        if notification:
            notification.is_read = True
            await self.db.commit()

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await self.db.commit()
        return result.rowcount
