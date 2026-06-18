from sqlalchemy import select

from app.domain.models import Notification
from app.repositories.base import Repository


class NotificationRepository(Repository[Notification]):
    model = Notification

    async def list_for_user(self, user_id: int, unread_only: bool = False) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        result = await self.session.execute(stmt.order_by(Notification.created_at.desc()))
        return list(result.scalars())
