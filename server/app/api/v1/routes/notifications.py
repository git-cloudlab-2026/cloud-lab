from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_session
from app.domain.models import User
from app.schemas.common import NotificationRead
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=dict)
async def list_notifications(unread_only: bool = False, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    rows = await NotificationService(session).list_for_user(user.id, unread_only)
    return {"data": [NotificationRead.model_validate(row) for row in rows]}


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_read(notification_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    row = await NotificationService(session).mark_read(notification_id, user.id)
    await session.commit()
    return {"data": NotificationRead.model_validate(row)}
