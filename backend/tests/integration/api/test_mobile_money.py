"""
Integration tests for /mobile-money endpoints.
CinetPay service and DB are mocked — no real external calls.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel, OrderModel, PaymentTransactionModel


pytestmark = pytest.mark.skip(
    reason="Mobile Money initiation is intentionally disabled in the JMJ Synergie manual-payment rollout."
)


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
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


def _make_order() -> OrderModel:
    o = OrderModel()
    o.id = ORDER_ID
    o.organization_id = ORG_ID
    o.order_number = "CMD-2026-00001"
    o.status = "confirmed"
    o.payment_status = "pending"
    o.currency = "XAF"
    o.total_cents = 50_000
    o.paid_cents = 0
    o.is_deleted = False
    o.created_at = datetime.now(timezone.utc)
    return o


def _make_txn() -> PaymentTransactionModel:
    t = PaymentTransactionModel()
    t.id = TXN_ID
    t.organization_id = ORG_ID
    t.order_id = ORDER_ID
    t.transaction_number = "MM-20260616-ABCD1234"
    t.transaction_type = "payment"
    t.status = "pending"
    t.method = "mobile_money"
    t.amount_cents = 50_000
    t.currency = "XAF"
    t.external_reference = "cinetpay-ref-001"
    t.notes = "orange_money"
    t.created_at = datetime.now(timezone.utc)
    t.transaction_date = datetime.now(timezone.utc)
    return t


def _mock_db(order: OrderModel | None = None, txn: PaymentTransactionModel | None = None):
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=order or txn)

    result = MagicMock()
    result.scalar_one_or_none.return_value = order or txn

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
async def test_initiate_payment_invalid_provider_returns_422():
    from app.main import app
    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/mobile-money/initiate", json={
            "order_id": str(ORDER_ID),
            "amount_cents": 50_000,
            "phone_number": "+22997000001",
            "provider": "paypal",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_initiate_payment_order_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(order=None)

    async with _app_client(user, db) as client:
        resp = await client.post("/api/v1/mobile-money/initiate", json={
            "order_id": str(ORDER_ID),
            "amount_cents": 50_000,
            "phone_number": "+22997000001",
            "provider": "orange_money",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_initiate_payment_no_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/mobile-money/initiate", json={
            "order_id": str(ORDER_ID),
            "amount_cents": 50_000,
            "phone_number": "+22997000001",
            "provider": "mtn_momo",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_initiate_payment_cinetpay_success_returns_201():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(order=_make_order())

    mock_cinetpay = AsyncMock()
    mock_cinetpay.initiate_payment = AsyncMock(return_value={
        "transaction_id": "cinetpay-txn-001",
        "payment_url": "https://checkout.cinetpay.com/pay/cinetpay-txn-001",
        "status": "pending",
    })

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.post("/api/v1/mobile-money/initiate", json={
                "order_id": str(ORDER_ID),
                "amount_cents": 50_000,
                "phone_number": "+22997000001",
                "provider": "orange_money",
                "currency": "XAF",
            })

    app.dependency_overrides.clear()
    assert resp.status_code == 201
    data = resp.json()
    assert "transaction_id" in data
    assert "payment_url" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_status_transaction_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(txn=None)

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400():
    """CinetPay webhook without valid signature must be rejected."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.post("/api/v1/mobile-money/webhook", json={
            "cpm_trans_id": "fake-txn",
            "cpm_site_id": "test-site",
            "cpm_amount": "50000",
            "cpm_currency": "XAF",
            "cpm_payment_date": "2026-06-16",
            "cpm_payment_time": "12:00:00",
            "cpm_error_message": "",
            "cpm_result": "00",
        })

    # 400 for bad/missing signature, or 422 for schema mismatch
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_initiate_payment_negative_amount_returns_400():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(order=_make_order())

    async with _app_client(user, db) as client:
        resp = await client.post("/api/v1/mobile-money/initiate", json={
            "order_id": str(ORDER_ID),
            "amount_cents": -1,
            "phone_number": "+22997000001",
            "provider": "orange_money",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_initiate_payment_cinetpay_failure_returns_502():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(order=_make_order())

    mock_cinetpay = AsyncMock()
    mock_cinetpay.initiate_payment = AsyncMock(side_effect=RuntimeError("provider down"))

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.post("/api/v1/mobile-money/initiate", json={
                "order_id": str(ORDER_ID),
                "amount_cents": 50_000,
                "phone_number": "+22997000001",
                "provider": "orange_money",
                "currency": "XAF",
            })

    app.dependency_overrides.clear()
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_webhook_success_updates_transaction_and_order():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    txn = _make_txn()
    order = _make_order()
    txn_result = MagicMock(scalar_one_or_none=MagicMock(return_value=txn))
    order_result = MagicMock(scalar_one_or_none=MagicMock(return_value=order))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[txn_result, order_result])
    db.commit = AsyncMock()

    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                json={"cpm_trans_id": "cinetpay-ref-001", "cpm_result": "00"},
                headers={"X-Cinetpay-Signature": "sig"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "completed"
    assert order.paid_cents == 50_000
    assert order.payment_status == "paid"


@pytest.mark.asyncio
async def test_webhook_invalid_json_payload_returns_400():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                content=b"not-json",
                headers={"X-Cinetpay-Signature": "sig", "Content-Type": "application/json"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_missing_transaction_id_returns_received():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                json={"cpm_result": "00"},
                headers={"X-Cinetpay-Signature": "sig"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


@pytest.mark.asyncio
async def test_webhook_unknown_transaction_returns_received():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.commit = AsyncMock()

    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                json={"cpm_trans_id": "unknown-ref", "cpm_result": "00"},
                headers={"X-Cinetpay-Signature": "sig"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


@pytest.mark.asyncio
async def test_webhook_failure_status_marks_transaction_failed():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    txn = _make_txn()
    txn_result = MagicMock(scalar_one_or_none=MagicMock(return_value=txn))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=txn_result)
    db.commit = AsyncMock()

    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                json={"cpm_trans_id": "cinetpay-ref-001", "cpm_result": "REFUSED"},
                headers={"X-Cinetpay-Signature": "sig"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "failed"
    assert txn.failure_reason == "CinetPay status: REFUSED"


@pytest.mark.asyncio
async def test_webhook_completed_without_order_id_skips_order_update():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    txn = _make_txn()
    txn.order_id = None
    txn_result = MagicMock(scalar_one_or_none=MagicMock(return_value=txn))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=txn_result)
    db.commit = AsyncMock()

    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                json={"cpm_trans_id": "cinetpay-ref-001", "cpm_result": "00"},
                headers={"X-Cinetpay-Signature": "sig"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "completed"


@pytest.mark.asyncio
async def test_webhook_completed_with_missing_order_skips_order_update():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    txn = _make_txn()
    txn_result = MagicMock(scalar_one_or_none=MagicMock(return_value=txn))
    order_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[txn_result, order_result])
    db.commit = AsyncMock()

    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db

    async def _db():
        yield db

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db

    mock_cinetpay = MagicMock()
    mock_cinetpay.verify_webhook_signature = MagicMock(return_value=True)

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://localhost",
        ) as client:
            resp = await client.post(
                "/api/v1/mobile-money/webhook",
                json={"cpm_trans_id": "cinetpay-ref-001", "cpm_result": "00"},
                headers={"X-Cinetpay-Signature": "sig"},
            )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "completed"


@pytest.mark.asyncio
async def test_status_no_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_status_already_settled_transaction_skips_remote_check():
    from app.main import app
    user = _make_user("manager")
    txn = _make_txn()
    txn.status = "completed"
    txn.notes = None
    db = _mock_db(txn=txn)

    mock_cinetpay = AsyncMock()

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["provider"] == "mobile_money"
    mock_cinetpay.verify_payment.assert_not_called()


@pytest.mark.asyncio
async def test_status_pending_transaction_remote_unchanged_skips_update():
    from app.main import app
    user = _make_user("manager")
    txn = _make_txn()
    db = _mock_db(txn=txn)

    mock_cinetpay = AsyncMock()
    mock_cinetpay.verify_payment = AsyncMock(return_value={"status": "pending"})

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "pending"


@pytest.mark.asyncio
async def test_status_pending_transaction_syncs_failed_remote_status():
    from app.main import app
    user = _make_user("manager")
    txn = _make_txn()
    db = _mock_db(txn=txn)

    mock_cinetpay = AsyncMock()
    mock_cinetpay.verify_payment = AsyncMock(return_value={"status": "failed"})

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "failed"


@pytest.mark.asyncio
async def test_status_pending_completed_without_order_id_skips_order_update():
    from app.main import app
    user = _make_user("manager")
    txn = _make_txn()
    txn.order_id = None
    db = _mock_db(txn=txn)

    mock_cinetpay = AsyncMock()
    mock_cinetpay.verify_payment = AsyncMock(return_value={"status": "completed"})

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "completed"


@pytest.mark.asyncio
async def test_status_pending_completed_with_missing_order_skips_order_update():
    from app.main import app
    user = _make_user("manager")
    txn = _make_txn()
    txn_result = MagicMock(scalar_one_or_none=MagicMock(return_value=txn))
    order_result = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[txn_result, order_result])
    db.commit = AsyncMock()

    mock_cinetpay = AsyncMock()
    mock_cinetpay.verify_payment = AsyncMock(return_value={"status": "completed"})

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "completed"


@pytest.mark.asyncio
async def test_status_pending_transaction_verify_error_is_swallowed():
    from app.main import app
    user = _make_user("manager")
    txn = _make_txn()
    db = _mock_db(txn=txn)

    mock_cinetpay = AsyncMock()
    mock_cinetpay.verify_payment = AsyncMock(side_effect=RuntimeError("provider down"))

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get(f"/api/v1/mobile-money/status/{TXN_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert txn.status == "pending"


@pytest.mark.asyncio
async def test_status_pending_transaction_syncs_completed_remote_status():
    from app.main import app

    user = _make_user("manager")
    txn = _make_txn()
    txn.notes = "Provider: orange_money | Tel: +22997000001"
    order = _make_order()
    txn_result = MagicMock(scalar_one_or_none=MagicMock(return_value=txn))
    order_result = MagicMock(scalar_one_or_none=MagicMock(return_value=order))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[txn_result, order_result])
    db.commit = AsyncMock()

    mock_cinetpay = AsyncMock()
    mock_cinetpay.verify_payment = AsyncMock(return_value={"status": "completed"})

    with patch("app.api.v1.endpoints.mobile_money.cinetpay_service", mock_cinetpay):
        async with _app_client(user, db) as client:
            resp = await client.get("/api/v1/mobile-money/status/cinetpay-ref-001")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["provider"] == "orange_money"
    assert order.payment_status == "paid"
