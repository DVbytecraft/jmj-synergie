from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.payment_dto import RefundResponseDTO
from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
REFUND_ID = uuid.UUID("abababab-0000-0000-0000-000000000001")
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


def _refund_dto(**overrides) -> RefundResponseDTO:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=REFUND_ID,
        refund_number="RFD-0001",
        order_id=ORDER_ID,
        client_id=CLIENT_ID,
        status="requested",
        reason="other",
        reason_detail="Produit retourne suite a un probleme de qualite",
        requested_amount_cents=5000,
        approved_amount_cents=None,
        currency="XAF",
        rejection_reason=None,
        notes=None,
        requested_at=now,
        approved_at=None,
        completed_at=None,
        created_at=now,
    )
    defaults.update(overrides)
    return RefundResponseDTO(**defaults)


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
    from app.api.v1.deps import get_current_user
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
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


@pytest.mark.asyncio
async def test_refunds_endpoints_cover_request_list_get_approve_and_reject() -> None:
    from app.api.v1.deps import (
        get_approve_refund_uc,
        get_list_refunds_uc,
        get_reject_refund_uc,
        get_request_refund_uc,
    )
    from app.main import app

    current = _make_user("manager")
    requested = _refund_dto()
    approved = _refund_dto(status="completed", approved_amount_cents=4000, completed_at=datetime.now(timezone.utc))
    rejected = _refund_dto(status="rejected", rejection_reason="Motif insuffisant")

    request_uc = AsyncMock()
    request_uc.execute = AsyncMock(return_value=requested)
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value={"items": [requested.model_dump(mode="json")], "total": 1, "skip": 0, "limit": 20})
    list_uc.get_by_id = AsyncMock(return_value=requested)
    approve_uc = AsyncMock()
    approve_uc.execute = AsyncMock(return_value=approved)
    reject_uc = AsyncMock()
    reject_uc.execute = AsyncMock(return_value=rejected)

    app.dependency_overrides[get_request_refund_uc] = lambda: request_uc
    app.dependency_overrides[get_list_refunds_uc] = lambda: list_uc
    app.dependency_overrides[get_approve_refund_uc] = lambda: approve_uc
    app.dependency_overrides[get_reject_refund_uc] = lambda: reject_uc

    try:
        async with _app_client(current) as client:
            request_resp = await client.post(
                "/api/v1/refunds/",
                json={
                    "order_id": str(ORDER_ID),
                    "original_transaction_id": str(TXN_ID),
                    "amount_cents": 5000,
                    "reason": "other",
                    "reason_detail": "Produit retourne suite a un probleme de qualite",
                },
            )
            list_resp = await client.get("/api/v1/refunds/?status=requested")
            get_resp = await client.get(f"/api/v1/refunds/{REFUND_ID}")
            approve_resp = await client.post(
                f"/api/v1/refunds/{REFUND_ID}/approve",
                json={"method": "cash", "approved_amount_cents": 4000},
            )
            reject_resp = await client.post(
                f"/api/v1/refunds/{REFUND_ID}/reject",
                json={"rejection_reason": "Motif insuffisant"},
            )

        assert request_resp.status_code == 201
        assert list_resp.status_code == 200
        assert get_resp.status_code == 200
        assert approve_resp.status_code == 200
        assert reject_resp.status_code == 200
        assert request_resp.json()["refund_number"] == "RFD-0001"
        assert list_resp.json()["total"] == 1
        assert approve_resp.json()["status"] == "completed"
        assert reject_resp.json()["status"] == "rejected"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_refund_not_found_returns_404() -> None:
    from app.api.v1.deps import get_list_refunds_uc
    from app.main import app

    user = _make_user("manager")
    list_uc = AsyncMock()
    list_uc.get_by_id = AsyncMock(return_value=None)
    app.dependency_overrides[get_list_refunds_uc] = lambda: list_uc

    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/refunds/{REFUND_ID}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
