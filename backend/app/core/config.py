"""
Application settings — Pydantic Settings v2.
Single source of truth for all configuration values.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "JMJ Synergie API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "production"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""   # Pour Alembic (psycopg2)
    DB_POOL_SIZE: int = 5        # 1 worker × 5 = 5 connections max de base
    DB_MAX_OVERFLOW: int = 10   # bursts jusqu'à 15 connexions max
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # recycle avant coupure des connexions idle par le provider managé
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
    ADMIN_RECOVERY_KEY: str = ""

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
    BREVO_SENDER_NAME: str = "JMJ Synergie"

    # ── Cloudinary (asset storage) ────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    USE_CLOUDINARY: bool = False

    # ── Company (PDF headers) ─────────────────────────────────────────────────
    COMPANY_NAME: str = "JMJ Synergie"
    COMPANY_ADDRESS: str = ""
    COMPANY_PHONE: str = ""
    COMPANY_EMAIL: str = ""
    COMPANY_TAX_ID: str = ""
    COMPANY_LOGO_PATH: str = "/app/storage/assets/logo.png"
    COMPANY_STAMP_PATH: str = "/app/storage/assets/stamp.png"

    # ── CinetPay (Mobile Money) ───────────────────────────────────────────────
    CINETPAY_API_KEY: str = ""
    CINETPAY_SITE_ID: str = ""

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Metrics ──────────────────────────────────────────────────────────────
    METRICS_TOKEN: str = ""
    METRICS_ALLOWED_IPS: str = ""

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
    def _looks_like_placeholder(value: str) -> bool:
        normalized = value.strip().lower()
        if not normalized:
            return False
        markers = (
            "change_me",
            "your-",
            "your_",
            "yourdomain",
            "votre-",
            "votre_",
            "devpassword",
            "devredispassword",
            "dev_secret_key",
            "admin123!dev",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _looks_like_placeholder_email(value: str) -> bool:
        normalized = value.strip().lower()
        if not normalized:
            return False
        return any(
            marker in normalized
            for marker in (
                "example.com",
                "yourdomain.com",
                "votre-domaine",
                "noreply@yourdomain.com",
            )
        )

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
            if not isinstance(parsed, list):  # pragma: no cover — unreachable: "[...]" JSON always parses to a list
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

        if self.FRONTEND_URL.startswith("http://localhost"):
            raise ValueError("FRONTEND_URL must point to the public frontend in production")

        if not self.FRONTEND_URL.startswith("https://"):
            raise ValueError("FRONTEND_URL must use https in production")

        for origin in self.allowed_origins_list:
            if not origin.startswith("https://"):
                raise ValueError("ALLOWED_ORIGINS entries must use https in production")

        required_secrets = {
            "DATABASE_URL": self.DATABASE_URL,
            "REDIS_URL": self.REDIS_URL,
            "SECRET_KEY": self.SECRET_KEY,
        }
        for label, value in required_secrets.items():
            if self._looks_like_placeholder(value):
                raise ValueError(f"{label} looks like a development or placeholder value in production")

        email_values = {
            "BREVO_SENDER_EMAIL": self.BREVO_SENDER_EMAIL,
            "SMTP_FROM": self.SMTP_FROM,
            "COMPANY_EMAIL": self.COMPANY_EMAIL,
        }
        for label, value in email_values.items():
            if value and self._looks_like_placeholder_email(value):
                raise ValueError(f"{label} must be replaced with a real production value")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
