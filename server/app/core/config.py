from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cloud Lab Control Center API"
    environment: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["mock", "oidc"] = "mock"
    database_url: str = Field(
        default="postgresql+asyncpg://cloud_lab_dev:cloud_lab_dev_password@localhost:5432/cloud_lab"
    )
    session_secret: str = "dev-only-change-me"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "null"]

    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None
    azure_redirect_uri: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
