"""
Integration tests for /portal endpoints.
DB is mocked — no real database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import (
    UserModel, OrderModel, ClientModel, ClientPortalTokenModel,
)


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
RAW_TOKEN = "testtoken123abc"


def _make_user(role: str = "manager") -> UserModel:
    u = UserModel()
    u.id = uuid.uuid4()
    u.organization_id = ORG_ID
    u.email = f"{role}@test.com"
    u.full_name = "Test User"
    u.role = role
    u.status = "active"
    u.is_deleted = False
    u.hashed_password = "x"
    u.refresh_token_jti = None
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _make_order() -> OrderModel:
    o = OrderModel()
    o.id = ORDER_ID
    o.organization_id = ORG_ID
    o.client_id = CLIENT_ID
    o.order_number = "CMD-2026-00001"
    o.status = "confirmed"
    o.payment_status = "pending"
    o.currency = "XAF"
    o.subtotal_cents = 100_000
    o.tax_cents = 18_000
    o.total_cents = 118_000
    o.paid_cents = 0
    o.is_deleted = False
    o.created_at = datetime.now(timezone.utc)
    o.updated_at = datetime.now(timezone.utc)

    client = ClientModel()
    client.id = CLIENT_ID
    client.full_name = "Amadou Traoré"
    client.company_name = None
    o.client = client
    o.documents = []
    o.items = []
    return o


def _make_portal_token(expired: bool = False) -> ClientPortalTokenModel:
    t = ClientPortalTokenModel()
    t.id = uuid.uuid4()
    t.organization_id = ORG_ID
    t.order_id = ORDER_ID
    t.token_hash = "fakehash"
    t.expires_at = (
        datetime.now(timezone.utc) - timedelta(days=1) if expired
        else datetime.now(timezone.utc) + timedelta(days=29)
    )
    t.revoked = False
    t.created_by = uuid.uuid4()
    t.created_at = datetime.now(timezone.utc)
    return t


def _mock_db(order: OrderModel | None = None, portal_token: ClientPortalTokenModel | None = None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = order or portal_token
    result.scalars.return_value.all.return_value = []

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


def _app_client(user: UserModel, db=None):
    from app.main import app
    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user
    from httpx import ASGITransport, AsyncClient

    if db is None:
        db = _mock_db()

    async def _db():
        yield db

    async def _user():
        return user

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_create_share_order_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(order=None)

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_share_no_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_share_returns_201_with_url():
    from app.main import app
    user = _make_user("manager")
    order = _make_order()
    db = _mock_db(order=order)

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 201
    data = resp.json()
    assert "url" in data
    assert "expires_at" in data
    assert "/portal/" in data["url"]


@pytest.mark.asyncio
async def test_public_portal_token_not_found_returns_404():
    """Unknown or invalid token must return 404 on the public portal endpoint."""
    from app.main import app
    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db
    from httpx import ASGITransport, AsyncClient

    db = _mock_db(portal_token=None)

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/api/v1/portal/{RAW_TOKEN}")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_share_order_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(order=None)

    async with _app_client(user, db) as client:
        resp = await client.delete(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 404
