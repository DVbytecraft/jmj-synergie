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
