from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import get_current_user
from app.db.session import get_session
from app.domain.models import User
from app.schemas.common import UserRead
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/mock-login/{user_id}", response_model=dict)
async def mock_login(user_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    user = await AuthService(session).mock_login(user_id)
    request.session["user_id"] = user.id
    return {"data": UserRead.model_validate(user)}


@router.get("/login")
async def login():
    settings = get_settings()
    if settings.auth_mode == "mock":
        return {"data": {"mode": "mock", "message": "Utilisez POST /api/v1/auth/mock-login/{user_id} en développement."}}
    raise ApiError(501, "oidc_not_configured", "Le flux OIDC réel doit être branché avec les identifiants Entra ID.")


@router.get("/callback")
async def callback():
    raise ApiError(501, "oidc_callback_not_configured", "Callback OIDC réservé à l'intégration Entra ID réelle.")


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"data": {"logged_out": True}}


@router.get("/me", response_model=dict)
async def me(user: User = Depends(get_current_user)):
    return {"data": UserRead.model_validate(user)}
