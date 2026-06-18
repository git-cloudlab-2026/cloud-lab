import secrets

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import get_current_user
from app.db.session import get_session
from app.domain.models import User
from app.schemas.common import UserRead
from app.services.auth_service import AuthService
from app.services.oidc_service import EntraOidcService

router = APIRouter()


@router.post("/mock-login/{user_id}", response_model=dict)
async def mock_login(user_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    if settings.auth_mode != "mock":
        raise ApiError(403, "mock_auth_disabled", "Le mode mock est desactive.")
    user = await AuthService(session).mock_login(user_id)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["auth_mode"] = "mock"
    return {"data": UserRead.model_validate(user)}


@router.get("/login")
async def login(request: Request):
    settings = get_settings()
    if settings.auth_mode == "mock":
        return {"data": {"mode": "mock", "message": "Utilisez POST /api/v1/auth/mock-login/{user_id} en developpement."}}

    oidc = EntraOidcService(settings)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = oidc.build_pkce()

    request.session["oidc_state"] = state
    request.session["oidc_nonce"] = nonce
    request.session["oidc_code_verifier"] = code_verifier

    authorization_url = await oidc.authorization_url(state=state, nonce=nonce, code_challenge=code_challenge)
    return RedirectResponse(authorization_url, status_code=302)


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    if settings.auth_mode != "oidc":
        raise ApiError(400, "oidc_disabled", "Le mode OIDC n'est pas active.")
    if error:
        raise ApiError(401, "oidc_provider_error", error_description or error)
    if not code or not state:
        raise ApiError(400, "oidc_missing_callback_params", "Callback OIDC incomplet.")

    expected_state = request.session.get("oidc_state")
    code_verifier = request.session.get("oidc_code_verifier")
    nonce = request.session.get("oidc_nonce")
    if not expected_state or not code_verifier or not nonce or state != expected_state:
        request.session.clear()
        raise ApiError(401, "oidc_invalid_state", "Etat OIDC invalide ou expire.")

    oidc = EntraOidcService(settings)
    token_set = await oidc.exchange_code(code, code_verifier)
    id_token = token_set.get("id_token")
    if not id_token:
        raise ApiError(401, "oidc_missing_id_token", "Entra ID n'a pas retourne de id_token.")

    claims = await oidc.verify_id_token(id_token, nonce)
    profile = oidc.extract_profile(claims)
    user = await AuthService(session).find_or_create_oidc_user(
        email=profile.email,
        full_name=profile.full_name,
        role=profile.role,
        class_name=profile.class_name,
        allow_student_auto_create=settings.oidc_auto_create_students,
    )

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["auth_mode"] = "oidc"
    await session.commit()

    return RedirectResponse("/portal/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"data": {"logged_out": True}}


@router.get("/me", response_model=dict)
async def me(user: User = Depends(get_current_user)):
    return {"data": UserRead.model_validate(user)}
