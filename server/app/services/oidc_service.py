import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebKey, jwt

from app.core.config import Settings
from app.core.errors import ApiError
from app.domain.enums import UserRole


@dataclass(frozen=True)
class OidcProfile:
    email: str
    full_name: str
    role: UserRole | None
    class_name: str | None
    groups: list[str]


class EntraOidcService:
    """Client OIDC Entra ID.

    Cette classe isole tout le protocole OIDC pour que les routes restent simples :
    generation de l'URL Microsoft, echange du code, verification du id_token et
    extraction du profil institutionnel.
    """

    def __init__(self, settings: Settings):
        settings.validate_oidc_settings()
        self.settings = settings

    async def discovery(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.settings.oidc_authority}/.well-known/openid-configuration")
            response.raise_for_status()
            return response.json()

    def build_pkce(self) -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    async def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        metadata = await self.discovery()
        params = {
            "client_id": self.settings.azure_client_id,
            "response_type": "code",
            "redirect_uri": self.settings.azure_redirect_uri,
            "response_mode": "query",
            "scope": self.settings.azure_scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{metadata['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        metadata = await self.discovery()
        payload = {
            "client_id": self.settings.azure_client_id,
            "client_secret": self.settings.azure_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.azure_redirect_uri,
            "code_verifier": code_verifier,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(metadata["token_endpoint"], data=payload)
        if response.status_code >= 400:
            raise ApiError(401, "oidc_token_exchange_failed", "Echange du code Entra ID refuse.")
        return response.json()

    async def verify_id_token(self, id_token: str, nonce: str) -> dict[str, Any]:
        metadata = await self.discovery()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(metadata["jwks_uri"])
            response.raise_for_status()
            key_set = JsonWebKey.import_key_set(response.json())

        claims = jwt.decode(
            id_token,
            key_set,
            claims_options={
                "iss": {"essential": True, "value": metadata["issuer"]},
                "aud": {"essential": True, "value": self.settings.azure_client_id},
                "exp": {"essential": True},
                "nonce": {"essential": True, "value": nonce},
            },
        )
        claims.validate(leeway=60)
        return dict(claims)

    def extract_groups(self, claims: dict[str, Any]) -> list[str]:
        raw_groups = claims.get("groups") or []
        if not isinstance(raw_groups, list):
            return []
        return [str(group_id) for group_id in raw_groups]

    def resolve_role_from_groups(self, groups: list[str]) -> tuple[UserRole | None, str | None]:
        mapping = self.settings.entra_group_mapping()
        for group_id in groups:
            mapped = mapping.get(group_id)
            if mapped:
                role, class_name = mapped
                return UserRole(role), class_name
        return None, None

    def extract_profile(self, claims: dict[str, Any]) -> OidcProfile:
        email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        full_name = claims.get("name") or email
        if not email:
            raise ApiError(403, "oidc_missing_email", "Le profil Entra ID ne contient pas d'email utilisable.")
        groups = self.extract_groups(claims)
        role, class_name = self.resolve_role_from_groups(groups)
        return OidcProfile(email=str(email).lower(), full_name=str(full_name), role=role, class_name=class_name, groups=groups)
