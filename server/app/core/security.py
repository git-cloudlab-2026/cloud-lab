from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_session
from app.domain.models import User
from app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(subject: int, email: str, role: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_access_token_expire_hours)
    payload = {"sub": str(subject), "email": email, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ApiError(401, "invalid_token", "Token JWT invalide ou expire.") from exc


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise ApiError(401, "invalid_token_subject", "Token JWT incomplet.")
        user = await UserRepository(session).get(int(user_id))
        if not user or not user.is_active:
            raise ApiError(401, "invalid_token_user", "Utilisateur JWT introuvable ou inactif.")
        return user

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
