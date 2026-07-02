"""
Integration tests for /payments endpoints.
Use case layer is mocked — no real DB required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.payment_dto import PaymentResponseDTO
from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
TXN_ID = uuid.UUID("ffffffff-0000-0000-0000-000000000001")


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


def _payment_dto(**overrides) -> PaymentResponseDTO:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=TXN_ID,
        transaction_number="TXN-202605-00001",
        order_id=ORDER_ID,
        client_id=CLIENT_ID,
        transaction_type="payment",
        status="completed",
        method="cash",
        amount_cents=50000,
        currency="XAF",
        external_reference=None,
        notes=None,
        completed_at=now,
        transaction_date=now,
        created_at=now,
    )
    defaults.update(overrides)
    return PaymentResponseDTO(**defaults)


def _mock_db() -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    result.one.return_value = SimpleNamespace(
        total=0, total_completed_cents=0, total_refunded_cents=0
    )
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
async def test_record_payment_returns_201():
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc

    user = _make_user("manager")
    dto = _payment_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post("/api/v1/payments", json={
                "order_id": str(ORDER_ID),
                "amount_cents": 50000,
                "method": "cash",
                "currency": "XAF",
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == str(TXN_ID)
        assert data["transaction_number"] == "TXN-202605-00001"
        assert data["amount_cents"] == 50000
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_payments_returns_200():
    from app.main import app

    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.get("/api/v1/payments")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["items"], list)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_record_payment_missing_order_id_returns_422():
    """Missing required field must trigger Pydantic validation error."""
    from app.main import app

    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/payments", json={
            "amount_cents": 50000,
            "method": "cash",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_record_payment_invalid_method_returns_422():
    """Unknown payment method must be rejected by schema validation."""
    from app.main import app

    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/payments", json={
            "order_id": str(ORDER_ID),
            "amount_cents": 50000,
            "method": "bitcoin",
            "currency": "XAF",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_record_payment_no_org_returns_403():
    """A user without organization_id must be blocked on payment endpoints."""
    from app.main import app
    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user
    from httpx import ASGITransport, AsyncClient

    user = _make_user("manager")
    user.organization_id = None

    db = _mock_db()

    async def _db():
        yield db

    async def _user():
        return user

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user

    token = create_access_token(user.id, user.role, user.full_name)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.get("/api/v1/payments")

    app.dependency_overrides.clear()
    assert resp.status_code == 403
