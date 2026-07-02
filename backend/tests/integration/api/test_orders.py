"""
Integration tests for /orders CRUD endpoints.
Use case layer is mocked — no real DB required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
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


def _app_client(user: UserModel):
    from app.main import app
    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user
    from httpx import ASGITransport, AsyncClient

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
