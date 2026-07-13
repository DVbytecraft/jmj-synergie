from __future__ import annotations

import sys
import types
import uuid

import pytest
from fastapi import Response

from app.api.v1.endpoints import auth
from app.infrastructure.database.models import UserModel


def _make_user() -> UserModel:
    user = UserModel()
    user.id = uuid.uuid4()
    user.organization_id = uuid.uuid4()
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.role = "manager"
    user.status = "active"
    user.is_deleted = False
    user.hashed_password = "x"
    user.refresh_token_jti = None
    return user


def test_validate_password_complexity_accepts_strong_password() -> None:
    assert auth._validate_password_complexity("StrongPass1") == "StrongPass1"


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Aa1", "au moins 8"),
        ("lowercase1", "une majuscule"),
        ("UPPERCASE1", "une minuscule"),
        ("NoDigitsHere", "un chiffre"),
    ],
)
def test_validate_password_complexity_rejects_weak_password(password: str, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        auth._validate_password_complexity(password)


@pytest.mark.asyncio
async def test_send_welcome_email_sends_escaped_html(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict] = []

    class FakeBrevoEmailService:
        async def send_custom(self, **kwargs):
            payloads.append(kwargs)
            return True

    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.services.email.brevo_service",
        types.SimpleNamespace(BrevoEmailService=FakeBrevoEmailService),
    )

    sent = await auth._send_welcome_email("a@example.com", "<Admin>", "Org & Co")

    assert sent is True
    assert payloads[0]["to_email"] == "a@example.com"
    assert "&lt;Admin&gt;" in payloads[0]["html_body"]
    assert "Org &amp; Co" in payloads[0]["html_body"]
    assert "/dashboard" in payloads[0]["html_body"]


@pytest.mark.asyncio
async def test_send_welcome_email_returns_false_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[tuple[str, dict]] = []

    class FakeBrevoEmailService:
        async def send_custom(self, **kwargs):
            raise RuntimeError("smtp down")

    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.services.email.brevo_service",
        types.SimpleNamespace(BrevoEmailService=FakeBrevoEmailService),
    )
    monkeypatch.setattr(auth._logger, "warning", lambda event, **kw: warnings.append((event, kw)))

    sent = await auth._send_welcome_email("a@example.com", "Admin", "Org")

    assert sent is False
    assert warnings == [("email.welcome.send_failed", {"to_email": "a@example.com", "error": "smtp down"})]


@pytest.mark.asyncio
async def test_send_password_reset_notice_sends_email(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict] = []

    class FakeBrevoEmailService:
        async def send_custom(self, **kwargs):
            payloads.append(kwargs)
            return True

    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.services.email.brevo_service",
        types.SimpleNamespace(BrevoEmailService=FakeBrevoEmailService),
    )

    sent = await auth._send_password_reset_notice("a@example.com", "Reset User")

    assert sent is True
    assert payloads[0]["to_email"] == "a@example.com"
    assert "Reset User" in payloads[0]["html_body"]


@pytest.mark.asyncio
async def test_send_password_reset_notice_returns_false_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[tuple[str, dict]] = []

    class FakeBrevoEmailService:
        async def send_custom(self, **kwargs):
            raise RuntimeError("mail fail")

    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.services.email.brevo_service",
        types.SimpleNamespace(BrevoEmailService=FakeBrevoEmailService),
    )
    monkeypatch.setattr(auth._logger, "warning", lambda event, **kw: warnings.append((event, kw)))

    sent = await auth._send_password_reset_notice("a@example.com", "Reset User")

    assert sent is False
    assert warnings == [
        ("email.password_reset_notice_failed", {"to_email": "a@example.com", "error": "mail fail"})
    ]


def test_issue_tokens_sets_refresh_cookie_and_updates_jti() -> None:
    user = _make_user()
    response = Response()

    tokens = auth._issue_tokens(user, response)

    assert tokens.token_type == "bearer"
    assert tokens.access_token
    assert user.refresh_token_jti is not None
    cookie_header = response.headers.get("set-cookie", "")
    assert "rt=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/api/v1/auth" in cookie_header
