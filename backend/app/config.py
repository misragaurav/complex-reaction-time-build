from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (.env in dev).

    Field names map to the environment variables documented in §9.2 of the
    PRD via pydantic-settings' default case-insensitive matching.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = None
    secret_key: str
    app_env: Literal["development", "production"] = "development"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    admin_email: str | None = None
    admin_password: str | None = None
    allowed_origins: str = ""

    @field_validator("secret_key")
    @classmethod
    def _check_secret_key_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long (NFR-5)")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.app_env == "development":
            return "sqlite:///./dev.db"
        raise RuntimeError("DATABASE_URL must be set when APP_ENV=production")

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def cookie_secure(self) -> bool:
        return self.app_env != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
