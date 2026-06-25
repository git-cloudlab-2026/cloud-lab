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

    # --- Provisioner ---
    # FIX Bug 3: valeur par défaut "mock" pour éviter le 409 en Docker sans config explicite.
    # Mettre PROVISIONER_MODE=terraform et REAL_PROVISIONING_ENABLED=true dans .env pour Infomaniak.
    provisioner_mode: Literal["mock", "terraform", "openstack"] = "mock"
    real_provisioning_enabled: bool = False

    mock_terraform_create_delay_seconds: float = 0.2
    mock_terraform_destroy_delay_seconds: float = 0.1

    # --- Terraform ---
    terraform_binary: str = "terraform"
    # FIX Bug 1: suppression des chemins Windows hardcodés — None = résolution dynamique depuis __file__
    terraform_module_dir: str | None = None
    terraform_work_dir: str = ".terraform-runs"
    terraform_openstack_cloud_name: str = "openstack"
    terraform_region: str = "dc4-a"
    terraform_project_prefix: str = "cloud-lab"
    terraform_network_cidr: str = "10.42.0.0/24"
    terraform_external_network_name: str = "ext-floating1"
    terraform_allowed_ssh_cidrs: list[str] = ["0.0.0.0/0"]
    terraform_default_flavor_name: str | None = "a1-ram2-disk20-perf1"
    terraform_image_name: str | None = "Ubuntu 24.04 LTS Noble Numbat"
    terraform_assign_floating_ip: bool = False
    terraform_ssh_public_key: str | None = None
    terraform_ssh_public_key_path: str | None = None

    # --- OpenStack direct ---
    os_auth_url: str | None = None
    os_project_name: str | None = None
    os_username: str | None = None
    os_password: str | None = None
    os_region_name: str = "dc4-a"
    os_user_domain_name: str = "Default"
    os_project_domain_name: str = "Default"
    openstack_network_id: str | None = None
    openstack_network_name: str | None = None
    openstack_keypair_name: str = "cloud-lab-key"
    openstack_security_group_name: str | None = None
    openstack_boot_timeout_seconds: int = 420

    # --- Scheduler ---
    lifecycle_scheduler_enabled: bool = True
    lifecycle_scheduler_interval_seconds: int = 3600

    # --- Email ---
    email_notifications_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Cloud Lab"
    smtp_use_tls: bool = True

    # FIX Bug 4: cors_origins est lu depuis .env et utilisé dans main.py (ne pas dupliquer)
    cors_origins: list[str] = [
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:5173",
        "null",
    ]

    # --- Azure / OIDC ---
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

    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
