"""
Integration tests for /organizations endpoints.
Database and storage are mocked to focus on endpoint behavior.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _make_user(role: str = "admin") -> UserModel:
    user = UserModel()
    user.id = uuid.uuid4()
    user.organization_id = ORG_ID
    user.email = f"{role}@test.com"
    user.full_name = "Admin User"
    user.role = role
    user.status = "active"
    user.is_deleted = False
    user.hashed_password = "x"
    user.refresh_token_jti = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _make_org():
    return SimpleNamespace(
        id=ORG_ID,
        code="ORG-001",
        name="JMJ",
        legal_name=None,
        tax_id=None,
        email=None,
        phone=None,
        address_line1=None,
        postal_code=None,
        city=None,
        country=None,
        rccm=None,
        website=None,
        bank_name=None,
        bank_account=None,
        logo_url=None,
        preferred_currency="XAF",
        is_active=True,
    )


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _app_client(user: UserModel, db: AsyncMock | None = None):
    from app.main import app
    from app.api.v1.deps import get_current_user
    from app.api.v1.endpoints import organizations
    from httpx import ASGITransport, AsyncClient

    if db is None:
        db = _mock_db()

    async def _db():
        yield db

    async def _user():
        return user

    app.dependency_overrides[organizations.get_db] = _db
    app.dependency_overrides[get_current_user] = _user

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_get_my_organization_returns_200():
    from app.main import app

    user = _make_user("manager")
    org = _make_org()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(org))

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/organizations/me")
        assert response.status_code == 200
        assert response.json()["name"] == "JMJ"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_organization_returns_404_without_org():
    from app.main import app

    user = _make_user("manager")
    user.organization_id = None

    try:
        async with _app_client(user) as client:
            response = await client.get("/api/v1/organizations/me")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_organization_returns_404_when_row_missing():
    """organization_id is set, but the row itself no longer exists in the DB."""
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/organizations/me")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_organization_rejects_unsupported_currency():
    from app.main import app

    user = _make_user("admin")

    try:
        async with _app_client(user) as client:
            response = await client.put(
                "/api/v1/organizations/me",
                json={"name": "JMJ", "preferred_currency": "BTC"},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_organization_normalizes_fields():
    from app.main import app

    user = _make_user("admin")
    org = _make_org()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(org))

    try:
        async with _app_client(user, db) as client:
            response = await client.put(
                "/api/v1/organizations/me",
                json={
                    "name": "  JMJ Synergie  ",
                    "email": "  org@example.com ",
                    "website": "  https://example.com ",
                    "preferred_currency": "EUR",
                },
            )
        assert response.status_code == 200
        assert response.json()["name"] == "JMJ Synergie"
        assert response.json()["preferred_currency"] == "EUR"
        assert org.email == "org@example.com"
        assert org.website == "https://example.com"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_organization_keeps_existing_currency_when_omitted():
    from app.main import app

    user = _make_user("admin")
    org = _make_org()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(org))

    try:
        async with _app_client(user, db) as client:
            response = await client.put(
                "/api/v1/organizations/me",
                json={"name": "JMJ"},
            )
        assert response.status_code == 200
        assert response.json()["preferred_currency"] == "XAF"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_organization_logo_rejects_unsupported_content_type():
    from app.main import app

    user = _make_user("admin")
    db = _mock_db()

    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/organizations/me/logo",
                files={"file": ("logo.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_organization_logo_rejects_oversized_file(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import organizations

    user = _make_user("admin")
    db = _mock_db()
    monkeypatch.setattr(organizations.settings, "MAX_FILE_SIZE_MB", 0)

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/organizations/me/logo",
                files={"file": ("logo.png", png, "image/png")},
            )
        assert response.status_code == 413
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_organization_logo_rejects_bad_magic_bytes():
    from app.main import app

    user = _make_user("admin")
    org = _make_org()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(org))

    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/organizations/me/logo",
                files={"file": ("logo.png", b"not-a-png", "image/png")},
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_organization_logo_updates_logo_url(monkeypatch):
    from app.main import app
    from app.infrastructure.services.storage import cloudinary_service

    user = _make_user("admin")
    org = _make_org()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(org))

    class FakeStorage:
        async def upload_asset(self, content, asset_type, user_id, filename):
            return ("https://cdn.example.com/org-logo.png", {})

    monkeypatch.setattr(cloudinary_service, "CloudinaryStorageService", FakeStorage)

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/organizations/me/logo",
                files={"file": ("logo.png", png, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["logo_url"] == "https://cdn.example.com/org-logo.png"
    finally:
        app.dependency_overrides.clear()
