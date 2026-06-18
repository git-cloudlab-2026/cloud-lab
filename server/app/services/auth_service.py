from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.domain.enums import UserRole
from app.domain.models import User
from app.repositories.users import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession):
        self.users = UserRepository(session)

    async def mock_login(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if not user or not user.is_active:
            raise ApiError(404, "user_not_found", "Utilisateur de demonstration introuvable.")
        return user

    async def find_or_create_oidc_user(
        self,
        *,
        email: str,
        full_name: str,
        role: UserRole | None,
        class_name: str | None,
        allow_student_auto_create: bool,
    ) -> User:
        user = await self.users.get_by_email(email)
        if not user:
            if role == UserRole.student and class_name and allow_student_auto_create:
                user = User(full_name=full_name, email=email, role=UserRole.student, class_name=class_name)
                self.users.add(user)
                await self.users.session.flush()
                return user
            raise ApiError(
                403,
                "unknown_institutional_user",
                (
                    f"{full_name} ({email}) est authentifie par Entra ID, "
                    "mais aucun compte applicatif ne lui est associe dans la table users."
                ),
            )
        if not user.is_active:
            raise ApiError(403, "inactive_user", "Compte applicatif desactive.")
        if role and user.role != role:
            raise ApiError(
                403,
                "role_mapping_mismatch",
                "Le role Entra ID ne correspond pas au role applicatif stocke.",
            )
        if class_name and user.class_name and user.class_name != class_name:
            raise ApiError(
                403,
                "class_mapping_mismatch",
                "La classe Entra ID ne correspond pas a la classe applicative stockee.",
            )
        return user
