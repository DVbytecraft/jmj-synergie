"""
Integration tests for GET /orders/kpi — dashboard KPI endpoint.
All DB calls are mocked; no real PostgreSQL required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


def _status_row(status: str, cnt: int, paid: int) -> SimpleNamespace:
    return SimpleNamespace(status=status, cnt=cnt, paid=paid)


def _mock_db_with_scalars(
    scalar_results: list,
    status_rows: list[SimpleNamespace] | None = None,
    recent_orders: list | None = None,
) -> AsyncMock:
    """
    Build a DB mock matching get_dashboard_kpi's sequential calls:
      scalar(total_orders) -> scalar(total_clients) -> execute(status rows)
      -> scalar(total_paid) -> execute(recent orders)
    """
    scalar_calls = [0]

    async def _scalar(query):
        idx = scalar_calls[0]
        scalar_calls[0] += 1
        return scalar_results[idx] if idx < len(scalar_results) else 0

    execute_calls = [0]

    async def _execute(query):
        idx = execute_calls[0]
        execute_calls[0] += 1
        result = MagicMock()
        if idx == 0:
            result.all.return_value = status_rows or []
        else:
            result.scalars.return_value.all.return_value = recent_orders or []
        return result

    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=_scalar)
    db.execute = AsyncMock(side_effect=_execute)
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        resp = await c.get("/api/v1/orders/kpi")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kpi_returns_expected_shape():
    """KPI endpoint must return all required fields with correct types."""
    from app.main import app
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user

    user = _make_user()

    db = _mock_db_with_scalars(
        scalar_results=[42, 10, 3_000_000],
        status_rows=[_status_row("delivered", 25, 4_500_000), _status_row("draft", 5, 500_000)],
    )

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
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

    db = _mock_db_with_scalars(scalar_results=[0, 0, 0])

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
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

    # Only "delivered" status in DB — others must default to 0
    db = _mock_db_with_scalars(
        scalar_results=[5, 2, 800_000],
        status_rows=[_status_row("delivered", 5, 1_000_000)],
    )

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            resp = await c.get("/api/v1/orders/kpi", headers=_auth_header())

        data = resp.json()
        assert data["orders_by_status"]["draft"] == 0
        assert data["orders_by_status"]["confirmed"] == 0
        assert data["orders_by_status"]["delivered"] == 5
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
