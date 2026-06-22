from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import ApiError


class Settings(BaseSettings):
    app_name: str = "Cloud Lab Control Center API"
    environment: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["mock", "oidc"] = "mock"
    database_url: str = Field(
        default="postgresql+asyncpg://cloud_lab_dev:cloud_lab_dev_password@localhost:5432/cloud_lab"
    )
    session_secret: str = "dev-only-change-me"
    jwt_secret: str = "dev-only-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 8
    mock_terraform_create_delay_seconds: float = 0.2
    mock_terraform_destroy_delay_seconds: float = 0.1
    lifecycle_scheduler_enabled: bool = True
    lifecycle_scheduler_interval_seconds: int = 3600
    cors_origins: list[str] = ["http://localhost:8000", "http://localhost:3000", "http://localhost:5173", "null"]

    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None
    azure_redirect_uri: str | None = None
    azure_scopes: str = "openid profile email User.Read GroupMember.Read.All"

    entra_admin_group_id: str | None = None
    entra_validator_group_id: str | None = None
    entra_teacher_group_id: str | None = None
    entra_student_e1_group_id: str | None = None
    entra_student_e2_group_id: str | None = None
    entra_student_e3_group_id: str | None = None
    entra_student_e4_group_id: str | None = None
    entra_student_e5_group_id: str | None = None
    oidc_auto_create_students: bool = True

    def validate_runtime(self) -> None:
        if self.environment == "production" and self.auth_mode != "oidc":
            raise RuntimeError("AUTH_MODE=oidc est obligatoire en production.")
        if self.environment == "production" and self.session_secret == "dev-only-change-me":
            raise RuntimeError("SESSION_SECRET doit etre change en production.")

    @property
    def oidc_authority(self) -> str:
        if not self.azure_tenant_id:
            raise ApiError(500, "oidc_missing_tenant", "AZURE_TENANT_ID est obligatoire en mode OIDC.")
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0"

    def validate_oidc_settings(self) -> None:
        missing = [
            name
            for name, value in {
                "AZURE_TENANT_ID": self.azure_tenant_id,
                "AZURE_CLIENT_ID": self.azure_client_id,
                "AZURE_CLIENT_SECRET": self.azure_client_secret,
                "AZURE_REDIRECT_URI": self.azure_redirect_uri,
            }.items()
            if not value
        ]
        if missing:
            raise ApiError(
                500,
                "oidc_missing_configuration",
                f"Configuration OIDC incomplete: {', '.join(missing)}.",
            )

    def entra_group_mapping(self) -> dict[str, tuple[str, str | None]]:
        mapping: dict[str, tuple[str, str | None]] = {}
        if self.entra_admin_group_id:
            mapping[self.entra_admin_group_id] = ("admin", None)
        if self.entra_validator_group_id:
            mapping[self.entra_validator_group_id] = ("validator", None)
        if self.entra_teacher_group_id:
            mapping[self.entra_teacher_group_id] = ("teacher", None)
        for class_name, group_id in {
            "E1": self.entra_student_e1_group_id,
            "E2": self.entra_student_e2_group_id,
            "E3": self.entra_student_e3_group_id,
            "E4": self.entra_student_e4_group_id,
            "E5": self.entra_student_e5_group_id,
        }.items():
            if group_id:
                mapping[group_id] = ("student", class_name)
        return mapping

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
