"""
Integration tests for auth endpoints.
Tests focus on the JTI refresh-token revocation we introduced in Fix 3.
The DB layer is mocked so no real PostgreSQL is required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_refresh_token
from app.infrastructure.database.models import UserModel


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


def _mock_db_returning(user: UserModel | None) -> AsyncMock:
    """Build a minimal AsyncSession mock whose execute() returns the given user."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    result.scalars.return_value.first.return_value = user

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.close = AsyncMock()
    return db


@pytest_asyncio.fixture
async def anon_client() -> AsyncClient:
    """Unauthenticated client — for auth-level endpoints (login, refresh, logout)."""
    from app.main import app
    from app.core.database import get_db

    # We'll set the override per-test via a factory helper
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── /refresh — JTI revocation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_valid_jti_returns_new_tokens():
    """A refresh token whose JTI matches the stored JTI must succeed."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=jti)

    # After _issue_tokens the user's JTI will be updated; we allow flush to succeed
    db = _mock_db_returning(user)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": token}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_wrong_jti_returns_401():
    """A revoked refresh token (JTI mismatch) must be rejected."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    old_token, _old_jti = create_refresh_token(user_id)
    _new_token, new_jti = create_refresh_token(user_id)

    # DB has the NEW jti stored (old one is revoked)
    user = _make_active_user(user_id, jti=new_jti)
    db = _mock_db_returning(user)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": old_token}
            )
        assert resp.status_code == 401
        assert "révoqué" in resp.json()["detail"].lower() or "expir" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_no_jti_stored_returns_401():
    """If the user has no JTI in DB (was logged out), refresh must fail."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, _jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=None)  # no JTI in DB
    db = _mock_db_returning(user)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": token}
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401():
    """A completely invalid (garbage) refresh token must return 401."""
    from app.main import app
    from app.core.database import get_db

    db = _mock_db_returning(None)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": "not.a.token"}
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── /logout ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_clears_jti():
    """Logout must set user.refresh_token_jti to None."""
    from app.main import app
    from app.core.database import get_db

    user_id = uuid.uuid4()
    token, jti = create_refresh_token(user_id)
    user = _make_active_user(user_id, jti=jti)
    db = _mock_db_returning(user)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/logout", json={"refresh_token": token}
            )
        assert resp.status_code == 200
        assert user.refresh_token_jti is None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_logout_with_invalid_token_still_succeeds():
    """Logout with an already-invalid token must return 200 (idempotent)."""
    from app.main import app
    from app.core.database import get_db

    db = _mock_db_returning(None)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/auth/logout", json={"refresh_token": "garbage.token.here"}
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
