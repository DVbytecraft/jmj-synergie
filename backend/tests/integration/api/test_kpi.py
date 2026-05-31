"""
Integration tests for GET /orders/kpi — dashboard KPI endpoint.
All DB calls are mocked; no real PostgreSQL required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


# ── Helpers ───────────────────────────────────────────────────────────────────

ORG_ID   = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
USER_ID  = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002")


def _make_user() -> UserModel:
    u = UserModel()
    u.id = USER_ID
    u.organization_id = ORG_ID
    u.email = "kpi@test.com"
    u.full_name = "KPI User"
    u.role = "admin"
    u.status = "active"
    u.is_deleted = False
    u.hashed_password = "x"
    u.refresh_token_jti = None
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _mock_db_with_scalars(scalar_results: list) -> AsyncMock:
    """Build a DB mock whose consecutive scalar() calls return the given values."""
    call_count = [0]

    async def _scalar(query):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(scalar_results):
            return scalar_results[idx]
        return 0

    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=_scalar)
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.close = AsyncMock()
    return db


def _auth_header() -> dict:
    token = create_access_token(USER_ID, "admin", "KPI User")
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kpi_requires_auth():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/orders/kpi")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kpi_returns_expected_shape():
    """KPI endpoint must return all required fields with correct types."""
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user

    user = _make_user()

    # Mock DB: gather() calls 5 coroutines in the endpoint.
    # We patch asyncio.gather to return controlled results.
    kpi_result = {
        "total_orders": 42,
        "total_clients": 10,
        "ca_total_cents": 5_000_000,
        "total_paid_cents": 3_000_000,
        "orders_by_status": {
            "draft": 5, "confirmed": 7, "in_progress": 3,
            "delivered": 25, "cancelled": 2, "refunded": 0,
        },
        "recent_orders": [],
    }

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # Patch the endpoint's gather call to return controlled data
        with patch(
            "app.api.v1.endpoints.orders.asyncio.gather",
            new=AsyncMock(return_value=(42, 10, ({"delivered": 25, "draft": 5}, 5_000_000), 3_000_000, [])),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/v1/orders/kpi", headers=_auth_header())

        assert resp.status_code == 200
        data = resp.json()
        assert "total_orders" in data
        assert "total_clients" in data
        assert "ca_total_cents" in data
        assert "total_paid_cents" in data
        assert "orders_by_status" in data
        assert "recent_orders" in data
        assert isinstance(data["recent_orders"], list)
        assert isinstance(data["orders_by_status"], dict)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_kpi_zero_data_returns_zeros():
    """KPI with no orders/clients must return zeros, not errors."""
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user

    user = _make_user()

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        with patch(
            "app.api.v1.endpoints.orders.asyncio.gather",
            new=AsyncMock(return_value=(0, 0, ({}, 0), 0, [])),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/v1/orders/kpi", headers=_auth_header())

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 0
        assert data["total_clients"] == 0
        assert data["ca_total_cents"] == 0
        assert data["total_paid_cents"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_kpi_no_org_returns_403():
    """A user without an organization must get 403."""
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user

    user = _make_user()
    user.organization_id = None  # no org

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/v1/orders/kpi", headers=_auth_header())
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_kpi_orders_by_status_defaults_to_zero():
    """Missing statuses in DB result must default to 0 in response."""
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user

    user = _make_user()

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # Only "delivered" status in DB — others must default to 0
        with patch(
            "app.api.v1.endpoints.orders.asyncio.gather",
            new=AsyncMock(return_value=(5, 2, ({"delivered": 5}, 1_000_000), 800_000, [])),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/v1/orders/kpi", headers=_auth_header())

        data = resp.json()
        assert data["orders_by_status"]["draft"] == 0
        assert data["orders_by_status"]["confirmed"] == 0
        assert data["orders_by_status"]["delivered"] == 5
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
