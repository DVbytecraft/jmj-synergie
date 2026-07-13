"""
Integration tests for /quotes endpoints.
DB is mocked — no real database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel, QuoteModel, ClientModel, QuoteItemModel


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


def _quote_item(**overrides):
    defaults = dict(
        description="Ciment",
        quantity=2,
        unit_price_cents=5000,
        product_id=None,
        position=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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
async def test_list_quotes_supports_filters_and_search():
    from app.main import app
    user = _make_user("manager")
    quote = _make_quote(status="sent")
    db = _mock_db(quote=quote)

    quotes_result = db.execute.return_value
    clients_result = MagicMock()
    clients_result.scalars.return_value.all.return_value = [_make_client()]
    db.execute = AsyncMock(side_effect=[quotes_result, clients_result])
    db.scalar = AsyncMock(return_value=1)

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/quotes?client_id={CLIENT_ID}&status=sent&search=DEV")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "sent"


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
async def test_create_quote_returns_201(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes

    user = _make_user("manager")
    client = _make_client()
    db = _mock_db(client=client)
    item_model = QuoteItemModel()
    item_model.id = uuid.uuid4()
    item_model.quote_id = QUOTE_ID
    item_model.product_id = None
    item_model.description = "Ciment"
    item_model.quantity = 2
    item_model.unit_price_cents = 5000
    item_model.total_cents = 10000
    item_model.position = 0

    db.scalar = AsyncMock(return_value=client)
    seq_result = MagicMock()
    seq_result.scalar_one.return_value = 7
    db.execute = AsyncMock(return_value=seq_result)

    async def _refresh(obj, attribute_names=None):
        obj.id = QUOTE_ID
        obj.quote_number = "DEV-2026-00007"
        obj.status = "draft"
        obj.items = [item_model]
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = datetime.now(timezone.utc)

    db.refresh = AsyncMock(side_effect=_refresh)
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    async with _app_client(user, db) as client_http:
        resp = await client_http.post("/api/v1/quotes", json={
            "client_id": str(CLIENT_ID),
            "currency": "XAF",
            "tax_rate": 18,
            "items": [{"description": "Ciment", "quantity": 2, "unit_price_cents": 5000}],
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 201
    data = resp.json()
    assert data["quote_number"] == "DEV-2026-00007"
    assert data["subtotal_cents"] == 10000
    assert data["tax_cents"] == 1800
    assert data["total_cents"] == 11800


@pytest.mark.asyncio
async def test_create_quote_client_missing_returns_404():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(client=None)
    db.scalar = AsyncMock(return_value=None)

    async with _app_client(user, db) as client:
        resp = await client.post("/api/v1/quotes", json={
            "client_id": str(CLIENT_ID),
            "items": [{"description": "Ciment", "quantity": 1, "unit_price_cents": 1000}],
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 404


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
async def test_get_quote_returns_200():
    from app.main import app
    user = _make_user("manager")
    quote = _make_quote()
    db = _mock_db(quote=quote)
    db.scalar = AsyncMock(return_value=_make_client())

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["quote_number"] == "DEV-2026-00001"


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
async def test_get_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.get(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_quote_client_lookup_returns_none_when_client_missing():
    """_fetch_client_name returns None (not an error) when the client row is gone."""
    from app.main import app
    user = _make_user("manager")
    quote = _make_quote()
    db = _mock_db(quote=quote)
    db.scalar = AsyncMock(return_value=None)

    async with _app_client(user, db) as client:
        resp = await client.get(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["client_name"] is None


@pytest.mark.asyncio
async def test_list_quotes_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.get("/api/v1/quotes")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.put(f"/api/v1/quotes/{QUOTE_ID}", json={"notes": "x"})

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_send_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/send")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_accept_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/accept")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reject_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/reject")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_convert_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/convert")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_quote_without_org_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.delete(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_quote_sets_valid_until():
    from app.main import app
    user = _make_user("manager")
    quote = _make_quote(status="draft")
    db = _mock_db(quote=quote)
    db.refresh = AsyncMock()
    db.scalar = AsyncMock(return_value=None)

    async with _app_client(user, db) as client:
        resp = await client.put(
            f"/api/v1/quotes/{QUOTE_ID}",
            json={"valid_until": "2026-12-31T00:00:00Z"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert quote.valid_until is not None


@pytest.mark.asyncio
async def test_send_quote_skips_email_when_client_has_no_email(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    client_no_email = _make_client()
    client_no_email.email = None
    db = _mock_db(quote=quote)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quote)))
    db.scalar = AsyncMock(return_value=client_no_email)
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    async with _app_client(user, db) as client_http:
        resp = await client_http.post(f"/api/v1/quotes/{QUOTE_ID}/send")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_send_quote_swallows_email_send_failure(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes
    from app.infrastructure.services.email import brevo_service

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    client = _make_client()
    db = _mock_db(quote=quote)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quote)))
    db.scalar = AsyncMock(return_value=client)
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    class BrokenBrevo:
        async def send_custom(self, **kwargs):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(brevo_service, "BrevoEmailService", BrokenBrevo)

    async with _app_client(user, db) as client_http:
        resp = await client_http.post(f"/api/v1/quotes/{QUOTE_ID}/send")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


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
async def test_update_quote_replaces_items_and_client(monkeypatch):
    from app.main import app

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    existing_item = SimpleNamespace(id=uuid.uuid4())
    new_client = _make_client()
    new_client.id = CLIENT_ID
    db = _mock_db(quote=quote)

    quote_result = MagicMock(scalar_one_or_none=MagicMock(return_value=quote))
    existing_items_result = MagicMock()
    existing_items_result.scalars.return_value.all.return_value = [existing_item]
    db.execute = AsyncMock(side_effect=[quote_result, existing_items_result])
    db.scalar = AsyncMock(side_effect=[new_client, new_client])
    db.refresh = AsyncMock()

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/quotes/{QUOTE_ID}", json={
            "client_id": str(CLIENT_ID),
            "items": [{"description": "Fer", "quantity": 3, "unit_price_cents": 2000, "position": 1}],
            "currency": "EUR",
            "notes": "Mise a jour",
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["subtotal_cents"] == 6000
    assert quote.currency == "EUR"
    assert quote.notes == "Mise a jour"
    db.delete.assert_awaited_once_with(existing_item)


@pytest.mark.asyncio
async def test_update_quote_missing_client_returns_404():
    from app.main import app

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    db = _mock_db(quote=quote)
    db.scalar = AsyncMock(return_value=None)

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/quotes/{QUOTE_ID}", json={"client_id": str(CLIENT_ID)})

    app.dependency_overrides.clear()
    assert resp.status_code == 404


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
async def test_send_quote_invalid_state_returns_400():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote(status="accepted"))

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/send")

    app.dependency_overrides.clear()
    assert resp.status_code == 400


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
async def test_accept_quote_returns_200_for_draft(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    db = _mock_db(quote=quote)
    db.scalar = AsyncMock(return_value=_make_client())
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/accept")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


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
async def test_convert_quote_returns_200_and_marks_converted(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes

    user = _make_user("manager")
    quote = _make_quote(status="accepted")
    order_id = uuid.uuid4()
    db = _mock_db(quote=quote)
    db.add = MagicMock(side_effect=lambda obj: setattr(obj, "id", order_id) if obj.__class__.__name__ == "OrderModel" and getattr(obj, "id", None) is None else None)

    quote_result = MagicMock(scalar_one_or_none=MagicMock(return_value=quote))
    seq_result = MagicMock()
    seq_result.scalar_one.return_value = 12
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [
        _quote_item(description="Ciment", quantity=2, unit_price_cents=5000, position=3)
    ]
    db.execute = AsyncMock(side_effect=[quote_result, seq_result, items_result])

    async def _refresh(obj, attribute_names=None):
        if obj is quote:
            obj.items = []

    db.refresh = AsyncMock(side_effect=_refresh)
    db.scalar = AsyncMock(return_value=_make_client())
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/convert")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "converted"
    assert quote.converted_to_order_id is not None


@pytest.mark.asyncio
async def test_delete_quote_returns_204_for_draft(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    db = _mock_db(quote=quote)
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    async with _app_client(user, db) as client:
        resp = await client.delete(f"/api/v1/quotes/{QUOTE_ID}")

    app.dependency_overrides.clear()
    assert resp.status_code == 204
    assert quote.is_deleted is True
    assert quote.deleted_at is not None


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


@pytest.mark.asyncio
async def test_create_quote_without_organization_returns_403():
    from app.main import app
    user = _make_user("manager")
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.post("/api/v1/quotes", json={
            "client_id": str(CLIENT_ID),
            "items": [{"description": "Test", "quantity": 1, "unit_price_cents": 1000}],
        })

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_send_quote_returns_200_when_draft(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes
    from app.infrastructure.services.email import brevo_service

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    client = _make_client()
    db = _mock_db(quote=quote)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quote)))
    db.scalar = AsyncMock(return_value=client)
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    class FakeBrevo:
        async def send_custom(self, **kwargs):
            return True

    monkeypatch.setattr(brevo_service, "BrevoEmailService", FakeBrevo)

    async with _app_client(user, db) as client_http:
        resp = await client_http.post(f"/api/v1/quotes/{QUOTE_ID}/send")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_reject_quote_returns_200_for_sent_quote(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import quotes

    user = _make_user("manager")
    quote = _make_quote(status="sent")
    db = _mock_db(quote=quote)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quote)))
    db.scalar = AsyncMock(return_value=_make_client())
    monkeypatch.setattr(quotes, "log_audit_event", AsyncMock())

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/reject")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_reject_quote_invalid_state_returns_400():
    from app.main import app
    user = _make_user("manager")
    db = _mock_db(quote=_make_quote(status="converted"))

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/reject")

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_quote_tax_rate_recalculates_totals():
    from app.main import app

    user = _make_user("manager")
    quote = _make_quote(status="draft")
    db = _mock_db(quote=quote)
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [_quote_item()]
    quote_result = MagicMock(scalar_one_or_none=MagicMock(return_value=quote))
    db.execute = AsyncMock(side_effect=[quote_result, items_result])
    db.scalar = AsyncMock(return_value=_make_client())

    async with _app_client(user, db) as client:
        resp = await client.put(f"/api/v1/quotes/{QUOTE_ID}", json={"tax_rate": 20})

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["tax_cents"] == 2000
    assert resp.json()["total_cents"] == 12000


@pytest.mark.asyncio
async def test_convert_quote_rejects_already_converted_quote():
    from app.main import app
    user = _make_user("manager")
    quote = _make_quote(status="accepted")
    quote.converted_to_order_id = uuid.uuid4()
    db = _mock_db(quote=quote)

    async with _app_client(user, db) as client:
        resp = await client.post(f"/api/v1/quotes/{QUOTE_ID}/convert")

    app.dependency_overrides.clear()
    assert resp.status_code == 400
