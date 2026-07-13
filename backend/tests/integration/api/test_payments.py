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


def _txn_model(**overrides):
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
        organization_id=ORG_ID,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_record_payment_returns_201(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    dto = _payment_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    monkeypatch.setattr(payments, "log_audit_event", AsyncMock())
    monkeypatch.setattr(payments, "publish_notification", AsyncMock())
    monkeypatch.setattr(payments, "enqueue_payment_receipt", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == str(TXN_ID)
        assert data["transaction_number"] == "TXN-202605-00001"
        assert data["amount_cents"] == 50000
        payments.publish_notification.assert_awaited_once()
        payments.enqueue_payment_receipt.assert_awaited_once()
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
async def test_list_payments_returns_items_and_aggregates():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    txn = _txn_model()
    db.execute = AsyncMock(side_effect=[
        MagicMock(one=MagicMock(return_value=SimpleNamespace(total=2, total_completed_cents=50000, total_refunded_cents=1000))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[txn])))),
    ])

    try:
        async with _app_client(user, db) as client:
            resp = await client.get("/api/v1/payments", params={"search": str(TXN_ID), "order_id": str(ORDER_ID)})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 2
        assert payload["total_completed_cents"] == 50000
        assert payload["total_refunded_cents"] == 1000
        assert payload["items"][0]["id"] == str(TXN_ID)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_missing_order_id_returns_422():
    from app.main import app

    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/payments", json={"amount_cents": 50000, "method": "cash"})

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_record_payment_invalid_method_returns_422():
    from app.main import app

    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(ORDER_ID),
                "amount_cents": 50000,
                "method": "bitcoin",
                "currency": "XAF",
            },
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_record_payment_no_org_returns_403():
    from app.main import app

    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.get("/api/v1/payments")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_record_payment_rejects_too_long_idempotency_key():
    from app.main import app

    user = _make_user("manager")
    long_key = "x" * 129

    async with _app_client(user) as client:
        resp = await client.post(
            "/api/v1/payments",
            json={
                "order_id": str(ORDER_ID),
                "amount_cents": 50000,
                "method": "cash",
                "currency": "XAF",
            },
            headers={"X-Idempotency-Key": long_key},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_record_payment_returns_cached_response_when_idempotency_key_reused(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    dto = _payment_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    redis = AsyncMock()
    redis.set = AsyncMock(return_value=False)
    redis.get = AsyncMock(return_value=dto.model_dump_json())
    monkeypatch.setattr(payments, "get_redis", lambda: redis)

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
                headers={"X-Idempotency-Key": "idem-1"},
            )
        assert resp.status_code == 201
        assert resp.json()["id"] == str(TXN_ID)
        mock_uc.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_returns_409_when_idempotent_request_is_stuck(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock()

    redis = AsyncMock()
    redis.set = AsyncMock(return_value=False)
    redis.get = AsyncMock(return_value="PROCESSING")
    monkeypatch.setattr(payments, "get_redis", lambda: redis)
    monkeypatch.setattr(payments.asyncio, "sleep", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
                headers={"X-Idempotency-Key": "idem-1"},
            )
        assert resp.status_code == 409
        mock_uc.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_claims_lock_and_caches_result(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    dto = _payment_dto()
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

    fake_redis = FakeRedis()
    monkeypatch.setattr(payments, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(payments, "log_audit_event", AsyncMock())
    monkeypatch.setattr(payments, "publish_notification", AsyncMock())
    monkeypatch.setattr(payments, "enqueue_payment_receipt", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
                headers={"X-Idempotency-Key": "idem-1"},
            )
        assert resp.status_code == 201
        mock_uc.execute.assert_awaited_once()
        assert fake_redis.cached_value is not None
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_swallows_cache_write_error_after_success(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    dto = _payment_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    class FakeRedis:
        async def set(self, key, value, nx=False, ex=None):
            if nx:
                return True
            raise RuntimeError("redis cache write failed")

    monkeypatch.setattr(payments, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(payments, "log_audit_event", AsyncMock())
    monkeypatch.setattr(payments, "publish_notification", AsyncMock())
    monkeypatch.setattr(payments, "enqueue_payment_receipt", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
                headers={"X-Idempotency-Key": "idem-1"},
            )
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_idempotent_wait_resolves_on_final_check(monkeypatch):
    """Regression: the cached value only appears on the very last poll after the loop exits."""
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    dto = _payment_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock()

    class FakeRedis:
        def __init__(self):
            self.get_calls = 0

        async def set(self, *args, **kwargs):
            return False

        async def get(self, key):
            self.get_calls += 1
            if self.get_calls >= 21:
                return dto.model_dump_json()
            return "PROCESSING"

    monkeypatch.setattr(payments, "get_redis", lambda: FakeRedis())
    monkeypatch.setattr(payments.asyncio, "sleep", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
                headers={"X-Idempotency-Key": "idem-1"},
            )
        assert resp.status_code == 201
        assert resp.json()["id"] == str(TXN_ID)
        mock_uc.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_deletes_lock_when_use_case_raises(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

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
    monkeypatch.setattr(payments, "get_redis", lambda: fake_redis)

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.post(
                    "/api/v1/payments",
                    json={
                        "order_id": str(ORDER_ID),
                        "amount_cents": 50000,
                        "method": "cash",
                        "currency": "XAF",
                    },
                    headers={"X-Idempotency-Key": "idem-1"},
                )
        assert len(fake_redis.deleted_keys) == 1
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_swallows_delete_error_after_use_case_failure(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=RuntimeError("boom"))

    class FakeRedis:
        async def set(self, key, value, nx=False, ex=None):
            return True

        async def delete(self, key):
            raise RuntimeError("redis delete failed")

    monkeypatch.setattr(payments, "get_redis", lambda: FakeRedis())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.post(
                    "/api/v1/payments",
                    json={
                        "order_id": str(ORDER_ID),
                        "amount_cents": 50000,
                        "method": "cash",
                        "currency": "XAF",
                    },
                    headers={"X-Idempotency-Key": "idem-1"},
                )
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_without_idempotency_key_propagates_use_case_error():
    """No X-Idempotency-Key header: failure path must skip the redis-delete branch entirely."""
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=RuntimeError("boom"))

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.post(
                    "/api/v1/payments",
                    json={
                        "order_id": str(ORDER_ID),
                        "amount_cents": 50000,
                        "method": "cash",
                        "currency": "XAF",
                    },
                )
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_fail_open_when_redis_is_unavailable(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    dto = _payment_dto(order_id=None)
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    class BrokenRedis:
        async def set(self, *args, **kwargs):
            raise RuntimeError("redis down")

    monkeypatch.setattr(payments, "get_redis", lambda: BrokenRedis())
    monkeypatch.setattr(payments, "log_audit_event", AsyncMock())
    monkeypatch.setattr(payments, "publish_notification", AsyncMock())
    monkeypatch.setattr(payments, "enqueue_payment_receipt", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
                headers={"X-Idempotency-Key": "idem-1"},
            )
        assert resp.status_code == 201
        mock_uc.execute.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_record_payment_skips_notification_and_receipt_without_organization_or_order(monkeypatch):
    from app.main import app
    from app.api.v1.deps import get_record_payment_uc
    from app.api.v1.endpoints import payments

    user = _make_user("manager")
    user.organization_id = None
    dto = _payment_dto(order_id=None)
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    monkeypatch.setattr(payments, "log_audit_event", AsyncMock())
    monkeypatch.setattr(payments, "publish_notification", AsyncMock())
    monkeypatch.setattr(payments, "enqueue_payment_receipt", AsyncMock())

    app.dependency_overrides[get_record_payment_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post(
                "/api/v1/payments",
                json={
                    "order_id": str(ORDER_ID),
                    "amount_cents": 50000,
                    "method": "cash",
                    "currency": "XAF",
                },
            )
        assert resp.status_code == 201
        payments.publish_notification.assert_not_awaited()
        payments.enqueue_payment_receipt.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_record_payment_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_transaction_returns_200():
    from app.main import app

    user = _make_user("manager")
    db = _mock_db()
    txn = _txn_model()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=txn)))

    try:
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/payments/{TXN_ID}")
        assert resp.status_code == 200
        assert resp.json()["transaction_number"] == "TXN-202605-00001"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_transaction_not_found_returns_404():
    from app.main import app

    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.get(f"/api/v1/payments/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_transaction_requires_organization():
    from app.main import app

    user = _make_user("manager")
    user.organization_id = None

    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/payments/{TXN_ID}")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
