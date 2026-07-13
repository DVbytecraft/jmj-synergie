"""
Integration tests for /portal endpoints.
DB is mocked - no real database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import (
    ClientModel,
    ClientPortalTokenModel,
    OrderModel,
    OrganizationModel,
    UserModel,
)


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
RAW_TOKEN = "testtoken123abc"


def _make_user(role: str = "manager") -> UserModel:
    user = UserModel()
    user.id = uuid.uuid4()
    user.organization_id = ORG_ID
    user.email = f"{role}@test.com"
    user.full_name = "Test User"
    user.role = role
    user.status = "active"
    user.is_deleted = False
    user.hashed_password = "x"
    user.refresh_token_jti = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _make_order() -> OrderModel:
    order = OrderModel()
    order.id = ORDER_ID
    order.organization_id = ORG_ID
    order.client_id = CLIENT_ID
    order.order_number = "CMD-2026-00001"
    order.status = "confirmed"
    order.payment_status = "pending"
    order.currency = "XAF"
    order.subtotal_cents = 100_000
    order.tax_cents = 18_000
    order.total_cents = 118_000
    order.paid_cents = 0
    order.is_deleted = False
    order.created_at = datetime.now(timezone.utc)
    order.updated_at = datetime.now(timezone.utc)

    client = ClientModel()
    client.id = CLIENT_ID
    client.full_name = "Amadou Traore"
    client.company_name = None
    order.client = client
    order.documents = []
    order.items = []
    return order


def _make_portal_token(expired: bool = False) -> ClientPortalTokenModel:
    token = ClientPortalTokenModel()
    token.id = uuid.uuid4()
    token.organization_id = ORG_ID
    token.order_id = ORDER_ID
    token.token_hash = "fakehash"
    token.expires_at = (
        datetime.now(timezone.utc) - timedelta(days=1)
        if expired
        else datetime.now(timezone.utc) + timedelta(days=29)
    )
    token.revoked = False
    token.created_by = uuid.uuid4()
    token.created_at = datetime.now(timezone.utc)
    return token


def _make_org(logo_url: str | None = "https://cdn.example.com/logo.png") -> OrganizationModel:
    organization = OrganizationModel()
    organization.id = ORG_ID
    organization.name = "JMJ Synergie Test"
    organization.logo_url = logo_url
    return organization


def _mock_db(
    order: OrderModel | None = None,
    portal_token: ClientPortalTokenModel | None = None,
):
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


def _mock_public_db(
    *,
    portal_token: ClientPortalTokenModel | None,
    order: OrderModel | None,
    client: ClientModel | None,
    organization: OrganizationModel | None,
    document_rows: list[tuple[str]],
):
    token_result = MagicMock()
    token_result.scalar_one_or_none.return_value = portal_token

    order_result = MagicMock()
    order_result.scalar_one_or_none.return_value = order

    client_result = MagicMock()
    client_result.scalar_one_or_none.return_value = client

    organization_result = MagicMock()
    organization_result.scalar_one_or_none.return_value = organization

    docs_result = MagicMock()
    docs_result.fetchall.return_value = document_rows

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            token_result,
            order_result,
            client_result,
            organization_result,
            docs_result,
        ]
    )
    return db


def _app_client(user: UserModel, db=None):
    from app.api.v1.deps import get_current_user
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
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
        base_url="http://localhost",
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
    db = _mock_db(order=_make_order())

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 201
    data = resp.json()
    assert "url" in data
    assert "expires_at" in data
    assert "/portal/" in data["url"]


@pytest.mark.asyncio
async def test_create_share_replaces_existing_tokens_before_commit():
    from app.main import app

    user = _make_user("manager")
    order_result = MagicMock()
    order_result.scalar_one_or_none.return_value = _make_order()

    tokens_result = MagicMock()
    tokens_result.scalars.return_value.all.return_value = [
        _make_portal_token(),
        _make_portal_token(),
    ]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[order_result, tokens_result])
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 201
    assert db.delete.await_count == 2
    db.commit.assert_awaited_once()
    assert db.add.call_count == 1


@pytest.mark.asyncio
async def test_public_portal_token_not_found_returns_404():
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    db = _mock_db(portal_token=None)

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get(f"/api/v1/portal/{RAW_TOKEN}")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_portal_returns_order_payload_with_deduplicated_documents():
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    order = _make_order()
    db = _mock_public_db(
        portal_token=_make_portal_token(),
        order=order,
        client=order.client,
        organization=_make_org(),
        document_rows=[("invoice",), ("invoice",), ("delivery_note",)],
    )

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get(f"/api/v1/portal/{RAW_TOKEN}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_number"] == order.order_number
    assert data["client_name"] == "Amadou Traore"
    assert data["organization_name"] == "JMJ Synergie Test"
    assert data["organization_logo_url"] == "https://cdn.example.com/logo.png"
    assert sorted(data["document_types"]) == ["delivery_note", "invoice"]


@pytest.mark.asyncio
async def test_public_portal_hides_non_public_organization_logo():
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    order = _make_order()
    db = _mock_public_db(
        portal_token=_make_portal_token(),
        order=order,
        client=order.client,
        organization=_make_org("uploads/logo.png"),
        document_rows=[],
    )

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get(f"/api/v1/portal/{RAW_TOKEN}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["organization_logo_url"] is None


@pytest.mark.asyncio
async def test_public_portal_returns_404_when_order_no_longer_exists():
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    token_result = MagicMock()
    token_result.scalar_one_or_none.return_value = _make_portal_token()

    order_result = MagicMock()
    order_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[token_result, order_result])

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
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


@pytest.mark.asyncio
async def test_revoke_share_no_org_returns_403():
    from app.main import app

    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.delete(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revoke_share_deletes_existing_tokens_and_returns_204():
    from app.main import app

    user = _make_user("manager")
    tokens_result = MagicMock()
    tokens_result.scalars.return_value.all.return_value = [
        _make_portal_token(),
        _make_portal_token(),
    ]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=tokens_result)
    db.commit = AsyncMock()
    db.delete = AsyncMock()

    async with _app_client(user, db) as client:
        resp = await client.delete(f"/api/v1/portal/orders/{ORDER_ID}/share")

    app.dependency_overrides.clear()
    assert resp.status_code == 204
    assert db.delete.await_count == 2
    db.commit.assert_awaited_once()
