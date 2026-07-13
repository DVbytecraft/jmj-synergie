"""
Integration tests for /stock endpoints.
DB is mocked — no real database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel, ProductModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
PROD_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000001")


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


def _make_product() -> ProductModel:
    p = ProductModel()
    p.id = PROD_ID
    p.organization_id = ORG_ID
    p.code = "PROD-001"
    p.name = "Ciment Portland"
    p.category = "Matériaux"
    p.unit = "sac"
    p.unit_price_cents = 500_000
    p.currency = "XAF"
    p.track_stock = True
    p.stock_quantity = 50
    p.low_stock_threshold = 10
    p.status = "active"
    p.is_deleted = False
    p.created_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    return p


def _mock_db(products: list | None = None):
    if products is None:
        products = []
    scalar_result = MagicMock()
    scalar_result.all.return_value = products
    scalar_result.scalar_one_or_none = MagicMock(return_value=products[0] if products else None)

    row = MagicMock()
    row.total = len(products)
    row.alerts = sum(
        1 for p in products
        if p.track_stock and p.stock_quantity is not None
        and p.low_stock_threshold is not None
        and p.stock_quantity <= p.low_stock_threshold
    )

    result = MagicMock()
    result.scalars.return_value = scalar_result
    result.one.return_value = row
    result.scalar_one_or_none.return_value = products[0] if products else None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
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
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_list_stock_returns_200():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db([_make_product()])

    async with _app_client(user, db) as client:
        resp = await client.get("/api/v1/stock")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "alerts_count" in data


@pytest.mark.asyncio
async def test_list_stock_alerts_only_filters_and_counts():
    from app.main import app
    user = _make_user("manager")
    low = _make_product()
    low.stock_quantity = 5
    healthy = _make_product()
    healthy.id = uuid.uuid4()
    healthy.code = "PROD-002"
    healthy.name = "Briques"
    healthy.stock_quantity = 25

    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _mock_db([low]).execute.return_value,
            _mock_db([low]).execute.return_value,
            _mock_db([low]).execute.return_value,
        ]
    )

    async with _app_client(user, db) as client:
        resp = await client.get("/api/v1/stock?alerts_only=true")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["alerts_count"] == 1
    assert data["items"][0]["is_low_stock"] is True


@pytest.mark.asyncio
async def test_list_stock_unauthenticated_returns_401():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get("/api/v1/stock")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_stock_product_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db([])  # empty — no product

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/stock/{PROD_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_stock_returns_product_details():
    from app.main import app
    user = _make_user("manager")
    product = _make_product()
    db = _mock_db([product])

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/stock/{PROD_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "PROD-001"
    assert data["track_stock"] is True
    assert data["is_low_stock"] is False


@pytest.mark.asyncio
async def test_adjust_stock_invalid_reason_returns_422():
    from app.main import app
    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/stock/{PROD_ID}/adjust", json={
            "delta": 10,
            "reason": "invalid_reason",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_adjust_stock_rejects_when_track_stock_disabled():
    from app.main import app
    user = _make_user("manager")
    product = _make_product()
    product.track_stock = False
    db = _mock_db([product])

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/stock/{PROD_ID}/adjust", json={
            "delta": 5,
            "reason": "restock",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_adjust_stock_rejects_negative_resulting_quantity():
    from app.main import app
    user = _make_user("manager")
    product = _make_product()
    product.stock_quantity = 2
    db = _mock_db([product])

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/stock/{PROD_ID}/adjust", json={
            "delta": -5,
            "reason": "loss",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422
    assert "Stock insuffisant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_adjust_stock_updates_quantity_and_refreshes_row():
    from app.main import app
    user = _make_user("manager")
    product = _make_product()
    db = _mock_db([product])
    db.refresh = AsyncMock()

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/stock/{PROD_ID}/adjust", json={
            "delta": 7,
            "reason": "restock",
            "note": "Livraison fournisseur",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["stock_quantity"] == 57
    db.flush.assert_awaited()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_adjust_stock_product_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db([])  # no product

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/stock/{PROD_ID}/adjust", json={
            "delta": 5,
            "reason": "restock",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_adjust_stock_operator_forbidden():
    from app.main import app
    user = _make_user("operator")

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/stock/{PROD_ID}/adjust", json={
            "delta": 5,
            "reason": "restock",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_config_stock_operator_forbidden():
    """Operators (not manager+) must be blocked from configuring stock."""
    from app.main import app
    user = _make_user("operator")

    async with _app_client(user) as client:
        resp = await client.put(f"/api/v1/stock/{PROD_ID}/config", json={
            "track_stock": True,
            "low_stock_threshold": 5,
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_config_stock_updates_threshold_and_quantity():
    from app.main import app
    user = _make_user("manager")
    product = _make_product()
    db = _mock_db([product])
    db.refresh = AsyncMock()

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/stock/{PROD_ID}/config", json={
            "track_stock": True,
            "low_stock_threshold": 8,
            "stock_quantity": 12,
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["low_stock_threshold"] == 8
    assert data["stock_quantity"] == 12
    db.flush.assert_awaited()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_config_stock_disables_tracking_without_touching_threshold_or_quantity():
    from app.main import app
    user = _make_user("manager")
    product = _make_product()
    db = _mock_db([product])
    db.refresh = AsyncMock()

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/stock/{PROD_ID}/config", json={
            "track_stock": False,
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["low_stock_threshold"] == 10
    assert data["stock_quantity"] == 50


@pytest.mark.asyncio
async def test_config_stock_product_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db([])

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/stock/{PROD_ID}/config", json={
            "track_stock": False,
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_stock_no_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.get("/api/v1/stock")

    app.dependency_overrides.clear()
    assert resp.status_code == 403
