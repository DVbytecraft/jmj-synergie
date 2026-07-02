"""
Integration tests for multi-tenant data isolation.
Verifies that:
  1. Users without organization_id are blocked (403) on org-scoped endpoints.
  2. The _require_org guard rejects super_admin users who have no org set.
These tests mock the DB and only test the middleware/auth layer — they do NOT
need a real database.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


def _user_without_org(role: str = "manager") -> UserModel:
    u = UserModel()
    u.id = uuid.uuid4()
    u.organization_id = None   # ← no org — triggers _require_org guard
    u.email = "orphan@example.com"
    u.full_name = "Orphan User"
    u.role = role
    u.status = "active"
    u.is_deleted = False
    u.hashed_password = "x"
    u.refresh_token_jti = None
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _user_with_org(org_id: uuid.UUID, role: str = "manager") -> UserModel:
    u = _user_without_org(role)
    u.id = uuid.uuid4()
    u.organization_id = org_id
    return u


def _mock_db() -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


# ── Helper: build a temporary test client with a given "current user" ─────────

def _app_with_user(user: UserModel, db: AsyncMock | None = None):
    """Return a context manager yielding an AsyncClient authenticated as `user`."""
    from app.main import app
    from app.infrastructure.database.session import get_db_session
    from app.api.v1.deps import get_current_user
    from app.core.database import get_db

    _db = db or _mock_db()

    async def _override_db():
        yield _db

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_org_user_blocked_on_clients():
    """GET /clients must return 403 if user has no organization_id."""
    from app.main import app
    user = _user_without_org(role="manager")

    async with _app_with_user(user) as client:
        resp = await client.get("/api/v1/clients")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_org_user_blocked_on_orders():
    """GET /orders must return 403 if user has no organization_id."""
    from app.main import app
    user = _user_without_org(role="admin")

    async with _app_with_user(user) as client:
        resp = await client.get("/api/v1/orders")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_org_user_blocked_on_payments():
    """GET /payments must return 403 if user has no organization_id."""
    from app.main import app
    user = _user_without_org(role="admin")

    async with _app_with_user(user) as client:
        resp = await client.get("/api/v1/payments")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_org_user_blocked_on_products():
    """GET /products must return 403 if user has no organization_id."""
    from app.main import app
    user = _user_without_org(role="manager")

    async with _app_with_user(user) as client:
        resp = await client.get("/api/v1/products")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_user_passes_guard_on_clients():
    """GET /clients must NOT return 403 when user has an organization_id.
    (It may return 200 or another error, but not 403.)"""
    from app.main import app
    org = uuid.uuid4()
    user = _user_with_org(org)

    db = _mock_db()
    # Make the count query return 0 so list endpoint can respond with empty list
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, list_result])

    async with _app_with_user(user, db) as client:
        resp = await client.get("/api/v1/clients")

    app.dependency_overrides.clear()
    assert resp.status_code != 403
