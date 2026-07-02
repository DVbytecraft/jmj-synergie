"""
Integration tests for /quotes endpoints.
DB is mocked — no real database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel, QuoteModel, ClientModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
QUOTE_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
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


def _make_client() -> ClientModel:
    c = ClientModel()
    c.id = CLIENT_ID
    c.organization_id = ORG_ID
    c.full_name = "Amadou Traoré"
    c.company_name = "Société Traoré SARL"
    c.email = "amadou@traore.bj"
    c.phone = "+229 97000001"
    c.is_deleted = False
    c.created_at = datetime.now(timezone.utc)
    return c


def _make_quote(status: str = "draft") -> QuoteModel:
    q = QuoteModel()
    q.id = QUOTE_ID
    q.organization_id = ORG_ID
    q.client_id = CLIENT_ID
    q.quote_number = "DEV-2026-00001"
    q.status = status
    q.currency = "XAF"
    q.subtotal_cents = 100_000
    q.tax_rate = Decimal("18")
    q.tax_cents = 18_000
    q.total_cents = 118_000
    q.notes = None
    q.valid_until = None
    q.is_deleted = False
    q.created_by = uuid.uuid4()
    q.created_at = datetime.now(timezone.utc)
    q.updated_at = datetime.now(timezone.utc)
    q.items = []
    q.client = _make_client()
    return q


def _mock_db(quote: QuoteModel | None = None, client: ClientModel | None = None):
    scalar = MagicMock()
    scalar.all.return_value = [quote] if quote else []
    scalar.scalar_one_or_none = MagicMock(return_value=quote)

    row = MagicMock()
    row.total = 1 if quote else 0
    row.next_val = 1

    result = MagicMock()
    result.scalars.return_value = scalar
    result.scalar_one_or_none.return_value = quote or client
    result.one.return_value = row
    result.scalar_one.return_value = 1

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
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_list_quotes_returns_200():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote())

    # list_quotes issues two db.execute() calls (quotes, then a client batch-fetch) —
    # give each its own result instead of the single shared one from _mock_db().
    quotes_result = db.execute.return_value
    clients_result = MagicMock()
    clients_result.scalars.return_value.all.return_value = [_make_client()]
    db.execute = AsyncMock(side_effect=[quotes_result, clients_result])
    db.scalar = AsyncMock(return_value=1)

    async with _app_client(user, db) as client:
        resp = await client.get("/api/v1/quotes")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_quote_missing_client_returns_422():
    from app.main import app
    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/quotes", json={
            "items": [{"description": "Ciment", "quantity": 10, "unit_price_cents": 5000}],
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_quote_empty_items_returns_422():
    from app.main import app
    user = _make_user("manager")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/quotes", json={
            "client_id": str(CLIENT_ID),
            "items": [],
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_quote_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=None)

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_quote_sent_status_returns_400():
    """Updating a non-draft quote must be rejected with 400."""
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote(status="sent"))

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/quotes/{QUOTE_ID}", json={
            "notes": "updated",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_draft_quote_not_found_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=None)

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/send")

    app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_accept_converted_quote_returns_400():
    """A converted quote cannot be accepted — invalid status transition."""
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote(status="converted"))

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/accept")

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_convert_rejected_quote_returns_400():
    """Rejected quotes cannot be converted to orders."""
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote(status="rejected"))

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/convert")

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_sent_quote_returns_400():
    """Only draft quotes can be deleted."""
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote(status="sent"))

    async with _app_client(user, db) as client:
        resp = await client.delete(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_operator_cannot_create_quote():
    """Operators must be blocked from creating quotes (manager+ required)."""
    from app.main import app
    user = _make_user("operator")

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/quotes", json={
            "client_id": str(CLIENT_ID),
            "items": [{"description": "Test", "quantity": 1, "unit_price_cents": 1000}],
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 403
