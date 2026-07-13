"""
Integration tests for /users endpoints.
Database and external services are mocked to keep the suite deterministic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _make_user(role: str = "admin") -> UserModel:
    user = UserModel()
    user.id = uuid.uuid4()
    user.organization_id = ORG_ID
    user.email = f"{role}@test.com"
    user.full_name = "Test User"
    user.role = role
    user.status = "active"
    user.is_deleted = False
    user.hashed_password = "hashed"
    user.refresh_token_jti = "jti"
    user.signature_path = None
    user.signature_text = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


def _app_client(user: UserModel, db: AsyncMock | None = None):
    from app.main import app
    from app.api.v1.deps import get_current_user
    from app.api.v1.endpoints import users
    from httpx import ASGITransport, AsyncClient

    if db is None:
        db = _mock_db()

    async def _db():
        yield db

    async def _user():
        return user

    app.dependency_overrides[users.get_db] = _db
    app.dependency_overrides[get_current_user] = _user

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_get_me_returns_current_user():
    from app.main import app

    user = _make_user("manager")
    try:
        async with _app_client(user) as client:
            response = await client.get("/api/v1/users/me")
        assert response.status_code == 200
        assert response.json()["email"] == user.email
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_name_strips_value_and_flushes(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    db = _mock_db()
    monkeypatch.setattr(users, "log_audit_event", AsyncMock())

    try:
        async with _app_client(user, db) as client:
            response = await client.patch("/api/v1/users/me", json={"full_name": "  Alice Doe  "})
        assert response.status_code == 200
        assert response.json()["full_name"] == "Alice Doe"
        assert user.full_name == "Alice Doe"
        db.flush.assert_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_change_my_password_rejects_bad_current_password(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    monkeypatch.setattr("app.core.security.verify_password", lambda plain, hashed: False)
    monkeypatch.setattr(users, "hash_password_async", AsyncMock(return_value="new-hash"))

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/users/me/change-password",
                json={"current_password": "bad", "new_password": "Newpass123"},
            )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_change_my_password_updates_hash_and_clears_sessions(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    db = _mock_db()
    monkeypatch.setattr("app.core.security.verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(users, "hash_password_async", AsyncMock(return_value="new-hash"))
    monkeypatch.setattr(users, "log_audit_event", AsyncMock())

    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/change-password",
                json={"current_password": "Oldpass123", "new_password": "Newpass123"},
            )
        assert response.status_code == 204
        assert user.hashed_password == "new-hash"
        assert user.refresh_token_jti is None
        db.flush.assert_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_issuer_profile_uses_defaults_when_missing():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/users/me/profile")
        assert response.status_code == 200
        payload = response.json()
        assert payload["display_name"] == user.full_name
        assert payload["document_email"] == user.email
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_issuer_profile_creates_profile_and_updates_signature_text():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(
        profile_type="business",
        display_name=None,
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color=None,
        secondary_color=None,
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )
    db.execute = AsyncMock(side_effect=[_mock_result(None)])
    db.refresh = AsyncMock(side_effect=lambda obj: None)
    db.add = MagicMock(side_effect=lambda obj: profile.__dict__.update(obj.__dict__))

    try:
        async with _app_client(user, db) as client:
            response = await client.put(
                "/api/v1/users/me/profile",
                json={
                    "display_name": "  Ma Societe  ",
                    "phone": "  +237600000001 ",
                    "signature_text": "  La Direction  ",
                    "auto_send_documents": False,
                    "tax_included": False,
                },
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["display_name"] == "Ma Societe"
        assert payload["phone"] == "+237600000001"
        assert payload["auto_send_documents"] is False
        assert user.signature_text == "La Direction"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_issuer_profile_updates_existing_profile_without_signature_text():
    """Existing profile row + omitted signature_text: skip creation and skip signature update."""
    from app.main import app

    user = _make_user("manager")
    user.signature_text = "Original signature"
    db = _mock_db()
    profile = SimpleNamespace(
        profile_type="business",
        display_name="Old name",
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color=None,
        secondary_color=None,
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )
    db.execute = AsyncMock(return_value=_mock_result(profile))
    db.refresh = AsyncMock(side_effect=lambda obj: None)

    try:
        async with _app_client(user, db) as client:
            response = await client.put(
                "/api/v1/users/me/profile",
                json={"display_name": "New name"},
            )
        assert response.status_code == 200
        assert response.json()["display_name"] == "New name"
        assert user.signature_text == "Original signature"
        db.add.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_my_signature_text_clears_value():
    from app.main import app

    user = _make_user("manager")
    user.signature_text = "Ancienne signature"
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.put(
                "/api/v1/users/me/signature-text",
                json={"signature_text": "   "},
            )
        assert response.status_code == 200
        assert response.json()["signature_text"] is None
        assert user.signature_text is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_asset_rejects_mismatched_content_type():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/logo",
                files={"file": ("logo.png", b"not-a-png", "image/png")},
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_asset_rejects_invalid_asset_type():
    from app.main import app

    user = _make_user("manager")

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/avatar",
                files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\npayload", "image/png")},
            )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_asset_rejects_unsupported_declared_content_type():
    from app.main import app

    user = _make_user("manager")

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/logo",
                files={"file": ("logo.gif", b"GIF89a", "image/gif")},
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_asset_rejects_file_too_large(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    monkeypatch.setattr(users.settings, "MAX_FILE_SIZE_MB", 1)

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/logo",
                files={"file": ("logo.png", b"\x89PNG\r\n\x1a\n" + b"a" * (1024 * 1024 + 1), "image/png")},
            )
        assert response.status_code == 413
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_logo_updates_profile(monkeypatch):
    from app.main import app
    from app.infrastructure.services.storage import cloudinary_service

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(
        user_id=user.id,
        organization_id=user.organization_id,
        profile_type="business",
        display_name=None,
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color="#1a56db",
        secondary_color="#eff6ff",
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )

    class FakeStorage:
        async def upload_asset(self, content, asset_type, user_id, filename):
            return ("https://cdn.example.com/logo.png", {})

    db.execute = AsyncMock(return_value=_mock_result(profile))
    monkeypatch.setattr(cloudinary_service, "CloudinaryStorageService", FakeStorage)

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/logo",
                files={"file": ("logo.png", png, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["logo_path"] == "https://cdn.example.com/logo.png"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_logo_applies_extracted_colors(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users
    from app.infrastructure.services.storage import cloudinary_service

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(
        user_id=user.id,
        organization_id=user.organization_id,
        profile_type="business",
        display_name=None,
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color="#1a56db",
        secondary_color="#eff6ff",
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )

    class FakeStorage:
        async def upload_asset(self, content, asset_type, user_id, filename):
            return ("https://cdn.example.com/logo.png", {})

    db.execute = AsyncMock(return_value=_mock_result(profile))
    monkeypatch.setattr(cloudinary_service, "CloudinaryStorageService", FakeStorage)
    monkeypatch.setattr(users, "_extract_dominant_color", lambda content: "#336699")

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/logo",
                files={"file": ("logo.png", png, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["primary_color"] == "#336699"
        assert response.json()["secondary_color"] == "#e0e8ef"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_logo_keeps_custom_colors(monkeypatch):
    """A profile with already-customized colors must not be overwritten by extraction."""
    from app.main import app
    from app.api.v1.endpoints import users
    from app.infrastructure.services.storage import cloudinary_service

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(
        user_id=user.id,
        organization_id=user.organization_id,
        profile_type="business",
        display_name=None,
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color="#123456",
        secondary_color="#654321",
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )

    class FakeStorage:
        async def upload_asset(self, content, asset_type, user_id, filename):
            return ("https://cdn.example.com/logo.png", {})

    db.execute = AsyncMock(return_value=_mock_result(profile))
    monkeypatch.setattr(cloudinary_service, "CloudinaryStorageService", FakeStorage)
    monkeypatch.setattr(users, "_extract_dominant_color", lambda content: "#336699")

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/logo",
                files={"file": ("logo.png", png, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["primary_color"] == "#123456"
        assert response.json()["secondary_color"] == "#654321"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_stamp_updates_profile(monkeypatch):
    from app.main import app
    from app.infrastructure.services.storage import cloudinary_service

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(
        user_id=user.id,
        organization_id=user.organization_id,
        profile_type="business",
        display_name=None,
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color=None,
        secondary_color=None,
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )

    class FakeStorage:
        async def upload_asset(self, content, asset_type, user_id, filename):
            return ("https://cdn.example.com/stamp.png", {})

    db.execute = AsyncMock(return_value=_mock_result(profile))
    monkeypatch.setattr(cloudinary_service, "CloudinaryStorageService", FakeStorage)

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/stamp",
                files={"file": ("stamp.png", png, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["stamp_path"] == "https://cdn.example.com/stamp.png"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_user_signature_updates_user_signature_path(monkeypatch):
    from app.main import app
    from app.infrastructure.services.storage import cloudinary_service

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(
        user_id=user.id,
        organization_id=user.organization_id,
        profile_type="business",
        display_name=None,
        company_name=None,
        tax_id=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        postal_code=None,
        country=None,
        signature_title=None,
        footer_notes=None,
        document_email=None,
        auto_send_documents=True,
        tax_included=True,
        primary_color=None,
        secondary_color=None,
        font_family=None,
        logo_path=None,
        stamp_path=None,
    )

    class FakeStorage:
        async def upload_asset(self, content, asset_type, user_id, filename):
            return ("https://cdn.example.com/signature.png", {})

    db.execute = AsyncMock(return_value=_mock_result(profile))
    monkeypatch.setattr(cloudinary_service, "CloudinaryStorageService", FakeStorage)

    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                "/api/v1/users/me/profile/assets/signature",
                files={"file": ("signature.png", png, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["signature_path"] == "https://cdn.example.com/signature.png"
        assert user.signature_path == "https://cdn.example.com/signature.png"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_issuer_asset_redirects_remote_path():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(logo_path="https://cdn.example.com/logo.png", stamp_path=None)
    db.execute = AsyncMock(return_value=_mock_result(profile))

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/users/me/profile/assets/logo", follow_redirects=False)
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "https://cdn.example.com/logo.png"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_stamp_asset_redirects_remote_path():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    profile = SimpleNamespace(logo_path=None, stamp_path="https://cdn.example.com/stamp.png")
    db.execute = AsyncMock(return_value=_mock_result(profile))

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/users/me/profile/assets/stamp", follow_redirects=False)
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "https://cdn.example.com/stamp.png"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_issuer_asset_rejects_invalid_asset_type():
    from app.main import app

    user = _make_user("manager")

    try:
        async with _app_client(user) as client:
            response = await client.get("/api/v1/users/me/profile/assets/avatar")
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_issuer_asset_returns_404_when_missing():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/users/me/profile/assets/logo")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_signature_asset_rejects_path_outside_storage(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    with TemporaryDirectory() as tmp:
        outside = Path(tmp).parent / "signature.png"
        outside.write_bytes(b"png")
        user.signature_path = str(outside)
        monkeypatch.setattr(users.settings, "STORAGE_PATH", tmp)

        try:
            async with _app_client(user, db) as client:
                response = await client.get("/api/v1/users/me/profile/assets/signature")
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_signature_asset_returns_404_when_local_file_missing(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    with TemporaryDirectory() as tmp:
        user.signature_path = str(Path(tmp) / "missing.png")
        monkeypatch.setattr(users.settings, "STORAGE_PATH", tmp)

        try:
            async with _app_client(user, db) as client:
                response = await client.get("/api/v1/users/me/profile/assets/signature")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_my_signature_asset_returns_local_file(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import users

    user = _make_user("manager")
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "signature.png"
        file_path.write_bytes(b"png")
        user.signature_path = str(file_path)
        monkeypatch.setattr(users.settings, "STORAGE_PATH", tmp)

        try:
            async with _app_client(user, db) as client:
                response = await client.get("/api/v1/users/me/profile/assets/signature")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_users_returns_current_admin():
    from app.main import app

    user = _make_user("admin")

    try:
        async with _app_client(user) as client:
            response = await client.get("/api/v1/users")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["email"] == user.email
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_user_is_forbidden_in_single_tenant_mode():
    from app.main import app

    user = _make_user("admin")

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/users",
                json={
                    "email": "new@example.com",
                    "full_name": "New User",
                    "password": "Validpass1",
                    "role": "operator",
                },
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_user_is_forbidden_in_single_tenant_mode():
    from app.main import app

    user = _make_user("admin")

    try:
        async with _app_client(user) as client:
            response = await client.delete(f"/api/v1/users/{uuid.uuid4()}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_user_create_requires_password_complexity():
    from app.api.v1.endpoints.users import UserCreate

    with pytest.raises(ValidationError):
        UserCreate(
            email="new@example.com",
            full_name="New User",
            password="alllowercase1",
            role="operator",
        )


def test_user_create_requires_lowercase_when_other_rules_pass():
    from app.api.v1.endpoints.users import UserCreate

    with pytest.raises(ValidationError):
        UserCreate(
            email="new@example.com",
            full_name="New User",
            password="ALLUPPERCASE1",
            role="operator",
        )


def test_user_create_requires_digit_when_letters_present():
    from app.api.v1.endpoints.users import UserCreate

    with pytest.raises(ValidationError):
        UserCreate(
            email="new@example.com",
            full_name="New User",
            password="NoDigitsHere",
            role="operator",
        )


def test_change_password_request_requires_password_complexity():
    from app.api.v1.endpoints.users import ChangePasswordRequest

    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="old", new_password="NOLOWERCASE1")


def test_change_password_request_requires_uppercase_when_other_rules_pass():
    from app.api.v1.endpoints.users import ChangePasswordRequest

    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="old", new_password="lowercase1")


def test_change_password_request_requires_digit_when_other_rules_pass():
    from app.api.v1.endpoints.users import ChangePasswordRequest

    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="old", new_password="NoDigitsHere")
