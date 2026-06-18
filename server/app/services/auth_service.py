from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.domain.models import User
from app.repositories.users import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession):
        self.users = UserRepository(session)

    async def mock_login(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if not user or not user.is_active:
            raise ApiError(404, "user_not_found", "Utilisateur de démonstration introuvable.")
        return user

    async def find_or_create_oidc_user(self, email: str, full_name: str) -> User:
        user = await self.users.get_by_email(email)
        if not user:
            raise ApiError(
                403,
                "unknown_institutional_user",
                "Utilisateur authentifié par Entra ID mais absent de la table users.",
            )
        return user
