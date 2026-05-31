"""
Application settings — Pydantic Settings v2.
Single source of truth for all configuration values.
"""
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Biloz API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "production"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""   # Pour Alembic (psycopg2)
    DB_POOL_SIZE: int = 5        # 1 worker × 5 = 5 connections max de base
    DB_MAX_OVERFLOW: int = 10   # bursts jusqu'à 15 connexions max
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = ""
    TRUSTED_HOSTS: str = "*"
    FRONTEND_URL: str = "http://localhost:3000"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_PATH: str = "/app/storage"
    MAX_FILE_SIZE_MB: int = 10

    # ── Email ─────────────────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    # ── Brevo (transactional email) ───────────────────────────────────────────
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = ""
    BREVO_SENDER_NAME: str = "Biloz"

    # ── Cloudinary (asset storage) ────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    USE_CLOUDINARY: bool = False

    # ── Company (PDF headers) ─────────────────────────────────────────────────
    COMPANY_NAME: str = "Biloz"
    COMPANY_ADDRESS: str = ""
    COMPANY_PHONE: str = ""
    COMPANY_EMAIL: str = ""
    COMPANY_TAX_ID: str = ""
    COMPANY_LOGO_PATH: str = "/app/storage/assets/logo.png"
    COMPANY_STAMP_PATH: str = "/app/storage/assets/stamp.png"

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Pagination ────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ── Derived ───────────────────────────────────────────────────────────────
    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"

    @staticmethod
    def _parse_list_env(value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []

        raw = value.strip()
        if raw.startswith("[") and raw.endswith("]"):
            import json

            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("Expected a JSON array")
            return [str(item).strip() for item in parsed if str(item).strip()]

        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return self._parse_list_env(self.ALLOWED_ORIGINS)

    @property
    def trusted_hosts_list(self) -> list[str]:
        hosts = self._parse_list_env(self.TRUSTED_HOSTS)
        # Wildcard means allow all — never narrow it down automatically.
        # Render's health probe uses an internal IP as Host header, which would
        # otherwise be rejected when ALLOWED_ORIGINS is set.
        if not hosts or hosts == ["*"]:
            return ["*"]
        return hosts

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_strength(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def set_sync_url(self) -> "Settings":
        if not self.DATABASE_URL_SYNC:
            self.DATABASE_URL_SYNC = self.DATABASE_URL.replace(
                "postgresql+asyncpg://", "postgresql+psycopg2://"
            )
        return self

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if not self.is_production:
            return self

        if not self.allowed_origins_list:
            raise ValueError("ALLOWED_ORIGINS must be set in production")

        # A wildcard mixed with specific origins is a misconfiguration:
        # the browser honours the specific origin, not the wildcard,
        # but the intent is clearly wrong and can mask a security hole.
        origins = self.allowed_origins_list
        if "*" in origins and len(origins) > 1:
            raise ValueError(
                "ALLOWED_ORIGINS must not mix '*' with specific origins in production. "
                "Either allow all origins ('*') or list specific ones — not both."
            )
        if "*" in origins:
            raise ValueError(
                "ALLOWED_ORIGINS must not be '*' in production. "
                "List the exact frontend origin(s) instead."
            )

        if self.trusted_hosts_list == ["*"]:
            raise ValueError("TRUSTED_HOSTS must not be '*' in production")

        has_brevo = bool(self.BREVO_API_KEY and self.BREVO_SENDER_EMAIL)
        has_smtp = bool(self.SMTP_HOST and self.SMTP_FROM)
        if not (has_brevo or has_smtp):
            raise ValueError(
                "Transactional email must be configured in production "
                "(BREVO_API_KEY + BREVO_SENDER_EMAIL or SMTP_HOST + SMTP_FROM)"
            )

        if self.FRONTEND_URL.startswith("http://localhost"):
            raise ValueError("FRONTEND_URL must point to the public frontend in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
