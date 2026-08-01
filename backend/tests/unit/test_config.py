from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://user:StrongDbPass_123!@db.example.com:5432/jmj",
        "REDIS_URL": "redis://:StrongRedisPass_123!@redis.example.com:6379/0",
        "SECRET_KEY": "a" * 32,
        "ENVIRONMENT": "development",
        "DEBUG": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_parse_list_env_supports_csv() -> None:
    settings = make_settings(ALLOWED_ORIGINS="https://a.example, https://b.example")

    assert settings.allowed_origins_list == ["https://a.example", "https://b.example"]


def test_parse_list_env_passes_through_list() -> None:
    settings = make_settings()

    assert settings._parse_list_env(["https://a.example"]) == ["https://a.example"]


def test_is_testing_property() -> None:
    settings = make_settings(ENVIRONMENT="testing")

    assert settings.is_testing is True
    assert settings.is_production is False


def test_database_sync_url_respects_explicit_value() -> None:
    settings = make_settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/app",
        DATABASE_URL_SYNC="postgresql+psycopg2://custom:custom@db:5432/app",
    )

    assert settings.DATABASE_URL_SYNC == "postgresql+psycopg2://custom:custom@db:5432/app"


def test_production_rejects_bare_wildcard_origin() -> None:
    with pytest.raises(ValidationError, match="must not be '\\*' in production"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="*",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_allows_missing_transactional_email_config() -> None:
    settings = make_settings(
        ENVIRONMENT="production",
        ALLOWED_ORIGINS="https://app.example.com",
        TRUSTED_HOSTS="api.example.com",
        FRONTEND_URL="https://app.example.com",
    )

    assert settings.is_production is True


def test_parse_list_env_supports_json_array() -> None:
    settings = make_settings(ALLOWED_ORIGINS='["https://a.example", "https://b.example"]')

    assert settings.allowed_origins_list == ["https://a.example", "https://b.example"]


def test_trusted_hosts_defaults_to_wildcard_when_empty() -> None:
    settings = make_settings(TRUSTED_HOSTS="")

    assert settings.trusted_hosts_list == ["*"]


def test_database_sync_url_is_derived_from_async_url() -> None:
    settings = make_settings(DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/app")

    assert settings.DATABASE_URL_SYNC == "postgresql+psycopg2://user:pass@db:5432/app"


def test_short_secret_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY must be at least 32 characters"):
        make_settings(SECRET_KEY="too-short")


def test_production_rejects_missing_allowed_origins() -> None:
    with pytest.raises(ValidationError, match="ALLOWED_ORIGINS must be set in production"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_mixed_wildcard_origins() -> None:
    with pytest.raises(ValidationError, match="must not mix '\\*' with specific origins"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="*,https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_wildcard_trusted_hosts() -> None:
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS must not be '\\*' in production"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="*",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_localhost_frontend_url() -> None:
    with pytest.raises(ValidationError, match="FRONTEND_URL must point to the public frontend"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="http://localhost:3000",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_accepts_smtp_configuration_without_brevo() -> None:
    settings = make_settings(
        ENVIRONMENT="production",
        ALLOWED_ORIGINS="https://app.example.com",
        TRUSTED_HOSTS="api.example.com",
        FRONTEND_URL="https://app.example.com",
        SMTP_HOST="smtp.example.com",
        SMTP_FROM="noreply@jmjsynergie.com",
    )

    assert settings.is_production is True


def test_production_rejects_non_https_frontend_url() -> None:
    with pytest.raises(ValidationError, match="FRONTEND_URL must use https in production"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="http://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_non_https_allowed_origin() -> None:
    with pytest.raises(ValidationError, match="ALLOWED_ORIGINS entries must use https in production"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="http://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_placeholder_secret_values() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY looks like a development or placeholder value in production"):
        make_settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev_secret_key_64_chars_minimum_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_placeholder_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL looks like a development or placeholder value in production"):
        make_settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:devpassword@db:5432/app",
            ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
        )


def test_production_rejects_placeholder_sender_email() -> None:
    with pytest.raises(ValidationError, match="BREVO_SENDER_EMAIL must be replaced with a real production value"):
        make_settings(
            ENVIRONMENT="production",
            ALLOWED_ORIGINS="https://app.example.com",
            TRUSTED_HOSTS="api.example.com",
            FRONTEND_URL="https://app.example.com",
            BREVO_API_KEY="brevo-key",
            BREVO_SENDER_EMAIL="noreply@example.com",
            COMPANY_EMAIL="contact@example.com",
        )
