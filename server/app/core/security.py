from collections.abc import Iterable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.session import get_session
from app.domain.models import User
from app.repositories.users import UserRepository


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise ApiError(401, "not_authenticated", "Connexion requise.")
    user = await UserRepository(session).get(int(user_id))
    if not user or not user.is_active:
        request.session.clear()
        raise ApiError(401, "invalid_session", "Session invalide.")
    return user


def require_roles(*roles: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in roles:
            raise ApiError(403, "forbidden_role", "Rôle insuffisant pour cette action.")
        return user

    return dependency


def role_in(user: User, roles: Iterable[str]) -> bool:
    return user.role.value in set(roles)
