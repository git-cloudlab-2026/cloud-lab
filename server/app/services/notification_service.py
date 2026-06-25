from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotificationType
from app.domain.models import Notification, User
from app.repositories.notifications import NotificationRepository
from app.services.email_service import EmailService


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = NotificationRepository(session)
        self.email = EmailService()

    def create(self, user_id: int, type_: NotificationType, title: str, message: str) -> Notification:
        notification = Notification(user_id=user_id, type=type_, title=title, message=message)
        self.session.add(notification)
        return notification

    async def create_and_email(
        self,
        user: User,
        type_: NotificationType,
        title: str,
        message: str,
        email_subject: str | None = None,
    ) -> Notification:
        notification = self.create(user.id, type_, title, message)
        await self.email.send(user.email, email_subject or title, message)
        return notification

    async def list_for_user(self, user_id: int, unread_only: bool = False) -> list[Notification]:
        return await self.repository.list_for_user(user_id, unread_only)

    async def mark_read(self, notification_id: int, user_id: int) -> Notification:
        notification = await self.repository.get(notification_id)
        if not notification or notification.user_id != user_id:
            from app.core.errors import ApiError

            raise ApiError(404, "notification_not_found", "Notification introuvable.")
        notification.is_read = True
        await self.session.flush()
        return notification
