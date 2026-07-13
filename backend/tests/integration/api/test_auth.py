"""
Integration tests for auth endpoints — cookie-based refresh token flow.

The refresh token is now stored as an HttpOnly cookie 'rt' (not in the
response body). Tests send the cookie via httpx cookies= parameter.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_refresh_token
from app.infrastructure.database.models import UserModel


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_active_user(user_id: uuid.UUID | None = None, jti: str | None = None) -> UserModel:
    u = UserModel()
    u.id = user_id or uuid.uuid4()
    u.organization_id = uuid.uuid4()
    u.email = "test@example.com"
    u.full_name = "Test User"
    u.role = "manager"
    u.status = "active"
    u.is_deleted = False
    u.hashed_password = "x"
    u.refresh_token_jti = jti
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _mock_db(user: UserModel | None) -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db


def _db_override(user: UserModel | None):
    async def _yield():
        yield _mock_db(user)
    return _yield


# ── /refresh — cookie-based ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_valid_cookie_returns_new_access_token():
    """Valid 'rt' cookie with matching JTI → returns new access_token."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=jti)

    app.dependency_overrides[get_db] = _db_override(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh", cookies={"rt": token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        # refresh_token must NOT appear in the body anymore
        assert "refresh_token" not in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_sets_new_rt_cookie():
    """After refresh, response must set a new 'rt' HttpOnly cookie."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=jti)

    app.dependency_overrides[get_db] = _db_override(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh", cookies={"rt": token})
        assert resp.status_code == 200
        # Cookie must be present in Set-Cookie header
        assert "rt" in resp.cookies
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_no_cookie_returns_401():
    """No cookie at all → 401 (session expired)."""
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_wrong_jti_returns_401():
    """Cookie with revoked JTI (user logged out or re-logged elsewhere) → 401."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    old_token, _old_jti = create_refresh_token(user_id)
    _new_token, new_jti = create_refresh_token(user_id)

    user = _make_active_user(user_id, jti=new_jti)  # DB stores NEW jti
    app.dependency_overrides[get_db] = _db_override(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh", cookies={"rt": old_token})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401():
    """Garbage cookie value → 401."""
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh", cookies={"rt": "not.a.jwt.token"})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_no_jti_in_db_returns_401():
    """User's refresh_token_jti is None in DB (was explicitly logged out) → 401."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, _jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=None)

    app.dependency_overrides[get_db] = _db_override(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh", cookies={"rt": token})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_inactive_user_returns_401():
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=jti)
    user.status = "disabled"

    app.dependency_overrides[get_db] = _db_override(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/refresh", cookies={"rt": token})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── /logout — cookie-based ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_clears_jti_and_deletes_cookie():
    """Valid 'rt' cookie → JTI set to None, Set-Cookie clears 'rt'."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=jti)

    app.dependency_overrides[get_db] = _db_override(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/logout", cookies={"rt": token})
        assert resp.status_code == 200
        assert user.refresh_token_jti is None
        # Cookie should be cleared (Max-Age=0 or expires in past)
        cookie_header = resp.headers.get("set-cookie", "")
        assert "rt=" in cookie_header or "rt" in resp.cookies
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_logout_no_cookie_still_succeeds():
    """Logout without any cookie → 200 (idempotent, nothing to revoke)."""
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/logout")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_logout_invalid_token_still_succeeds():
    """Logout with garbage cookie → 200 (no crash)."""
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/logout", cookies={"rt": "garbage.token.here"})
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_logout_user_not_found_still_succeeds():
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, _jti = create_refresh_token(user_id)

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/logout", cookies={"rt": token})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Déconnecté"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_success_returns_token_and_cookie(monkeypatch: pytest.MonkeyPatch):
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.endpoints import auth as auth_endpoint

    user = _make_active_user()
    user.failed_login_count = 2
    user.locked_until = datetime.now(timezone.utc)
    user.last_login_at = None
    db = _mock_db(user)

    async def _yield():
        yield db

    async def _verify_password(_plain: str, _hashed: str) -> bool:
        return True

    async def _normalize(_db, _user):
        return _user

    async def _audit(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_endpoint, "verify_password_async", _verify_password)
    monkeypatch.setattr(auth_endpoint, "normalize_single_tenant_user", _normalize)
    monkeypatch.setattr(auth_endpoint, "log_audit_event", _audit)

    app.dependency_overrides[get_db] = _yield
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/login",
                data={"username": user.email, "password": "Correct123"},
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert "rt" in resp.cookies
        assert user.failed_login_count == 0
        assert user.locked_until is None
        assert user.last_login_at is not None
        db.flush.assert_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_wrong_password_commits_failure_counter(monkeypatch: pytest.MonkeyPatch):
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.endpoints import auth as auth_endpoint

    user = _make_active_user()
    user.failed_login_count = 0
    db = _mock_db(user)

    async def _yield():
        yield db

    async def _verify_password(_plain: str, _hashed: str) -> bool:
        return False

    monkeypatch.setattr(auth_endpoint, "verify_password_async", _verify_password)

    app.dependency_overrides[get_db] = _yield
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/login",
                data={"username": user.email, "password": "Wrong123"},
            )
        assert resp.status_code == 401
        assert user.failed_login_count == 1
        db.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401_without_commit(monkeypatch: pytest.MonkeyPatch):
    """No matching user: skip the failure-counter branch entirely (no db.commit)."""
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.endpoints import auth as auth_endpoint

    db = _mock_db(None)

    async def _yield():
        yield db

    async def _verify_password(_plain: str, _hashed: str) -> bool:
        return False

    monkeypatch.setattr(auth_endpoint, "verify_password_async", _verify_password)

    app.dependency_overrides[get_db] = _yield
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/login",
                data={"username": "ghost@example.com", "password": "Whatever123"},
            )
        assert resp.status_code == 401
        db.commit.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_locks_account_after_max_attempts(monkeypatch: pytest.MonkeyPatch):
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.endpoints import auth as auth_endpoint
    from app.core.config import settings

    user = _make_active_user()
    user.failed_login_count = settings.MAX_LOGIN_ATTEMPTS - 1
    user.locked_until = None
    db = _mock_db(user)

    async def _yield():
        yield db

    async def _verify_password(_plain: str, _hashed: str) -> bool:
        return False

    monkeypatch.setattr(auth_endpoint, "verify_password_async", _verify_password)

    app.dependency_overrides[get_db] = _yield
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/login",
                data={"username": user.email, "password": "Wrong123"},
            )
        assert resp.status_code == 401
        assert user.failed_login_count == 0
        assert user.locked_until is not None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_rejects_locked_and_disabled_accounts(monkeypatch: pytest.MonkeyPatch):
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.endpoints import auth as auth_endpoint

    locked_user = _make_active_user()
    locked_user.locked_until = datetime.now(timezone.utc).replace(year=2099)

    app.dependency_overrides[get_db] = _db_override(locked_user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            locked_resp = await c.post(
                "/api/v1/auth/login",
                data={"username": locked_user.email, "password": "Anything123"},
            )
        assert locked_resp.status_code == 423
    finally:
        app.dependency_overrides.pop(get_db, None)

    disabled_user = _make_active_user()
    disabled_user.status = "disabled"
    async def _verify_password(_plain: str, _hashed: str) -> bool:
        return True
    monkeypatch.setattr(auth_endpoint, "verify_password_async", _verify_password)
    app.dependency_overrides[get_db] = _db_override(disabled_user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            disabled_resp = await c.post(
                "/api/v1/auth/login",
                data={"username": disabled_user.email, "password": "x"},
            )
        assert disabled_resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_forgot_password_always_returns_generic_message():
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
        assert resp.status_code == 200
        assert "Si cet email" in resp.json()["message"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_register_organization_returns_403():
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/register-organization",
                json={
                    "organization_name": "Org Test",
                    "email": "owner@example.com",
                    "full_name": "Owner Test",
                    "password": "StrongPass1",
                },
            )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_reset_password_updates_user_and_revokes_sessions(monkeypatch: pytest.MonkeyPatch):
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.endpoints import auth as auth_endpoint

    user = _make_active_user()
    user.is_email_verified = False
    user.password_reset_token = "reset"
    user.password_reset_expires_at = datetime.now(timezone.utc)
    user.reset_session_token = "session"
    user.reset_session_expires_at = datetime.now(timezone.utc)
    user.reset_otp_attempts = 4
    user.failed_login_count = 3
    user.refresh_token_jti = "jti"

    db = _mock_db(user)

    async def _yield():
        yield db

    async def _hash_password(password: str) -> str:
        return f"hashed::{password}"

    async def _send_notice(*args, **kwargs) -> bool:
        return True

    monkeypatch.setattr(auth_endpoint, "hash_password_async", _hash_password)
    monkeypatch.setattr(auth_endpoint, "_send_password_reset_notice", _send_notice)

    app.dependency_overrides[get_db] = _yield
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/reset-password",
                json={"email": user.email, "new_password": "StrongPass1"},
            )
        assert resp.status_code == 200
        assert user.hashed_password == "hashed::StrongPass1"
        assert user.is_email_verified is True
        assert user.refresh_token_jti is None
        assert user.password_reset_token is None
        assert user.reset_session_token is None
        assert user.failed_login_count == 0
        db.flush.assert_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_reset_password_unknown_user_returns_404():
    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = _db_override(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.post(
                "/api/v1/auth/reset-password",
                json={"email": "ghost@example.com", "new_password": "StrongPass1"},
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
