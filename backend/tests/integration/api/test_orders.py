"""
Integration tests for /orders CRUD endpoints.
Use case layer is mocked — no real DB required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.order_dto import OrderResponseDTO, OrderListResponseDTO
from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")


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


def _order_dto(**overrides) -> OrderResponseDTO:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=ORDER_ID,
        order_number="CMD-202605-0001",
        client_id=CLIENT_ID,
        status="draft",
        payment_status="unpaid",
        currency="XAF",
        subtotal_cents=100000,
        tax_rate=Decimal("0.19"),
        tax_cents=19000,
        discount_cents=0,
        shipping_cents=0,
        total_cents=119000,
        delivered_subtotal_cents=0,
        delivered_tax_cents=0,
        delivered_total_cents=0,
        paid_cents=0,
        refunded_cents=0,
        balance_due_cents=119000,
        has_reliquat=False,
        fully_delivered=False,
        days_overdue=0,
        purchase_order_ref=None,
        notes=None,
        due_date=None,
        delivery_date=None,
        delivered_at=None,
        items=[],
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return OrderResponseDTO(**defaults)


def _mock_db() -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


def _app_client(user: UserModel, db: AsyncMock | None = None):
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


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_order_returns_201():
    from app.main import app
    from app.api.v1.deps import get_create_order_uc

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post("/api/v1/orders", json={
                "client_id": str(CLIENT_ID),
                "currency": "XAF",
                "tax_rate": 0.19,
                "items": [
                    {
                        "description": "Service conseil",
                        "quantity": 1,
                        "unit_price_cents": 100000,
                        "unit": "unit",
                        "sort_order": 1,
                    }
                ],
            })
        assert resp.status_code == 201
        assert resp.json()["id"] == str(ORDER_ID)
        assert resp.json()["order_number"] == "CMD-202605-0001"
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_without_idempotency_key_propagates_use_case_error():
    """No x-idempotency-key header: failure path must skip the redis-delete branch entirely."""
    from app.main import app
    from app.api.v1.deps import get_create_order_uc

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=RuntimeError("boom"))

    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.post("/api/v1/orders", json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [
                        {"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}
                    ],
                })
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_orders_returns_200():
    from app.main import app
    from app.api.v1.deps import get_list_orders_uc

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(
        return_value=OrderListResponseDTO(items=[], total=0, skip=0, limit=20)
    )

    app.dependency_overrides[get_list_orders_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.get("/api/v1/orders")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(get_list_orders_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_order_returns_200():
    from app.main import app
    from app.api.v1.deps import get_order_uc

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/orders/{ORDER_ID}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
    finally:
        app.dependency_overrides.pop(get_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_order_not_found_returns_404():
    from app.main import app
    from app.api.v1.deps import get_order_uc
    from app.core.exceptions import EntityNotFoundError

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=EntityNotFoundError("Order", ORDER_ID))

    app.dependency_overrides[get_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/orders/{ORDER_ID}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_confirm_order_returns_200():
    from app.main import app
    from app.api.v1.deps import get_confirm_order_uc

    user = _make_user("manager")
    dto = _order_dto(status="confirmed")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_confirm_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(f"/api/v1/orders/{ORDER_ID}/confirm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"
    finally:
        app.dependency_overrides.pop(get_confirm_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_order_returns_204():
    from app.main import app
    from app.api.v1.deps import get_delete_order_uc

    user = _make_user("admin")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=None)

    app.dependency_overrides[get_delete_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.delete(f"/api/v1/orders/{ORDER_ID}")
        assert resp.status_code == 204
    finally:
        app.dependency_overrides.pop(get_delete_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_order_returns_200():
    from app.main import app
    from app.api.v1.deps import get_update_order_uc

    user = _make_user("manager")
    dto = _order_dto(notes="Updated")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_update_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.patch(
                f"/api/v1/orders/{ORDER_ID}",
                json={"notes": "Updated", "tax_rate": 0.19},
            )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated"
    finally:
        app.dependency_overrides.pop(get_update_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_order_returns_200():
    from app.main import app
    from app.api.v1.deps import get_cancel_order_uc

    user = _make_user("manager")
    dto = _order_dto(status="cancelled")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_cancel_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(f"/api/v1/orders/{ORDER_ID}/cancel", json={"reason": "Client request"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
    finally:
        app.dependency_overrides.pop(get_cancel_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_order_item_returns_201():
    from app.main import app
    from app.api.v1.deps import get_add_item_uc

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_add_item_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                f"/api/v1/orders/{ORDER_ID}/items",
                json={
                    "description": "Service",
                    "quantity": 2,
                    "unit_price_cents": 50000,
                    "unit": "unit",
                    "sort_order": 1,
                },
            )
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.pop(get_add_item_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_remove_order_item_returns_200():
    from app.main import app
    from app.api.v1.deps import get_remove_item_uc

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)
    item_id = uuid.uuid4()

    app.dependency_overrides[get_remove_item_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.delete(f"/api/v1/orders/{ORDER_ID}/items/{item_id}")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_remove_item_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_delivery_returns_200():
    from app.main import app
    from app.api.v1.deps import get_record_delivery_uc

    user = _make_user("manager")
    dto = _order_dto(status="delivered", fully_delivered=True)
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)
    item_id = uuid.uuid4()

    app.dependency_overrides[get_record_delivery_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                f"/api/v1/orders/{ORDER_ID}/deliveries",
                json=[{"item_id": str(item_id), "quantity": 1}],
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"
    finally:
        app.dependency_overrides.pop(get_record_delivery_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_kpi_returns_aggregates():
    user = _make_user("manager")
    db = _mock_db()
    recent_order = SimpleNamespace(
        id=ORDER_ID,
        order_number="CMD-001",
        status="confirmed",
        total_cents=119000,
        currency="XAF",
        created_at=datetime.now(timezone.utc),
    )
    status_rows = [
        SimpleNamespace(status="draft", cnt=2, paid=1000),
        SimpleNamespace(status="confirmed", cnt=1, paid=5000),
    ]
    db.scalar = AsyncMock(side_effect=[3, 4, 12000])
    db.execute = AsyncMock(side_effect=[
        MagicMock(all=MagicMock(return_value=status_rows)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[recent_order])))),
    ])

    from app.main import app
    try:
        async with _app_client(user, db) as client:
            resp = await client.get("/api/v1/orders/kpi")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total_orders"] == 3
        assert payload["total_clients"] == 4
        assert payload["ca_total_cents"] == 6000
        assert payload["total_paid_cents"] == 12000
        assert payload["orders_by_status"]["draft"] == 2
        assert payload["recent_orders"][0]["order_number"] == "CMD-001"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_kpi_requires_organization():
    from app.main import app

    user = _make_user("manager")
    user.organization_id = None
    try:
        async with _app_client(user) as client:
            resp = await client.get("/api/v1/orders/kpi")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_returns_cached_idempotent_response(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    class FakeRedis:
        def __init__(self):
            self.calls = 0

        async def set(self, *args, **kwargs):
            return False

        async def get(self, key):
            self.calls += 1
            return dto.model_dump_json()

    monkeypatch.setattr(orders, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(orders, "log_audit_event", AsyncMock())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/orders",
                headers={"x-idempotency-key": "abc"},
                json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                },
            )
        assert resp.status_code == 201
        assert resp.json()["order_number"] == "CMD-202605-0001"
        mock_uc.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_returns_409_when_idempotent_request_is_stuck(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock()

    class FakeRedis:
        async def set(self, *args, **kwargs):
            return False

        async def get(self, key):
            return "PROCESSING"

    monkeypatch.setattr(orders, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(orders.asyncio, "sleep", AsyncMock())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/orders",
                headers={"x-idempotency-key": "abc"},
                json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                },
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_fail_open_when_redis_is_unavailable(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    class FakeRedis:
        async def set(self, *args, **kwargs):
            raise RuntimeError("redis down")

    monkeypatch.setattr(orders, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(orders, "log_audit_event", AsyncMock())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/orders",
                headers={"x-idempotency-key": "abc"},
                json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                },
            )
        assert resp.status_code == 201
        mock_uc.execute.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_claims_lock_and_caches_result(monkeypatch):
    """First request with a given idempotency key: lock acquired immediately, result cached."""
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    class FakeRedis:
        def __init__(self):
            self.cached_value = None

        async def set(self, key, value, nx=False, ex=None):
            if nx:
                return True
            self.cached_value = value
            return True

        async def delete(self, key):
            pass

    fake_redis = FakeRedis()
    monkeypatch.setattr(orders, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(orders, "log_audit_event", AsyncMock())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/orders",
                headers={"x-idempotency-key": "abc"},
                json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                },
            )
        assert resp.status_code == 201
        mock_uc.execute.assert_awaited_once()
        assert fake_redis.cached_value is not None
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_deletes_lock_when_use_case_raises(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=RuntimeError("boom"))

    class FakeRedis:
        def __init__(self):
            self.deleted_keys = []

        async def set(self, key, value, nx=False, ex=None):
            return True

        async def delete(self, key):
            self.deleted_keys.append(key)

    fake_redis = FakeRedis()
    monkeypatch.setattr(orders, "get_redis", lambda: fake_redis)
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.post(
                    "/api/v1/orders",
                    headers={"x-idempotency-key": "abc"},
                    json={
                        "client_id": str(CLIENT_ID),
                        "currency": "XAF",
                        "tax_rate": 0.19,
                        "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                    },
                )
        assert len(fake_redis.deleted_keys) == 1
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_swallows_delete_error_after_use_case_failure(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=RuntimeError("boom"))

    class FakeRedis:
        async def set(self, key, value, nx=False, ex=None):
            return True

        async def delete(self, key):
            raise RuntimeError("redis delete failed")

    monkeypatch.setattr(orders, "get_redis", lambda: FakeRedis())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.post(
                    "/api/v1/orders",
                    headers={"x-idempotency-key": "abc"},
                    json={
                        "client_id": str(CLIENT_ID),
                        "currency": "XAF",
                        "tax_rate": 0.19,
                        "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                    },
                )
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_swallows_cache_write_error_after_success(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    class FakeRedis:
        async def set(self, key, value, nx=False, ex=None):
            if nx:
                return True
            raise RuntimeError("redis cache write failed")

    monkeypatch.setattr(orders, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(orders, "log_audit_event", AsyncMock())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/orders",
                headers={"x-idempotency-key": "abc"},
                json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                },
            )
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_order_idempotent_wait_resolves_on_final_check(monkeypatch):
    """Regression: the cached value only appears on the very last poll after the loop exits."""
    from app.main import app
    from app.api.v1.deps import get_create_order_uc
    from app.api.v1.endpoints import orders

    user = _make_user("manager")
    dto = _order_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock()

    class FakeRedis:
        def __init__(self):
            self.get_calls = 0

        async def set(self, *args, **kwargs):
            return False

        async def get(self, key):
            self.get_calls += 1
            # 21 total get() calls happen (1 before the loop + 20 inside it).
            # Only resolve on the very last one, forcing the post-loop check to fire.
            if self.get_calls >= 21:
                return dto.model_dump_json()
            return "PROCESSING"

    monkeypatch.setattr(orders, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(orders.asyncio, "sleep", AsyncMock())
    app.dependency_overrides[get_create_order_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/orders",
                headers={"x-idempotency-key": "abc"},
                json={
                    "client_id": str(CLIENT_ID),
                    "currency": "XAF",
                    "tax_rate": 0.19,
                    "items": [{"description": "Service conseil", "quantity": 1, "unit_price_cents": 100000}],
                },
            )
        assert resp.status_code == 201
        assert resp.json()["order_number"] == "CMD-202605-0001"
        mock_uc.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_create_order_uc, None)
        app.dependency_overrides.clear()
