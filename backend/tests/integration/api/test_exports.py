"""
Integration tests for /exports endpoints.
DB is mocked — no real database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _make_user(role: str = "admin") -> UserModel:
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


def _mock_db(transactions: list | None = None):
    if transactions is None:
        transactions = []
    scalar = MagicMock()
    scalar.all.return_value = transactions

    result = MagicMock()
    result.scalars.return_value = scalar

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
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
async def test_export_csv_returns_200_with_correct_content_type():
    from app.main import app
    user = _make_user()
    db = _mock_db()

    async with _app_client(user, db) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "csv"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_export_xlsx_returns_200_with_correct_content_type():
    from app.main import app
    user = _make_user()
    db = _mock_db()

    async with _app_client(user, db) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "xlsx"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("content-type", "")
    assert 'journal-ventes-2026-01-01-2026-06-30.xlsx' in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_export_invalid_format_returns_400():
    from app.main import app
    user = _make_user()

    async with _app_client(user) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "pdf"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_date_range_reversed_returns_400():
    from app.main import app
    user = _make_user()

    async with _app_client(user) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-12-01", "end": "2026-01-01", "format": "csv"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_export_csv_contains_ohada_headers():
    """The CSV export must include OHADA journal column headers."""
    from app.main import app
    user = _make_user()
    db = _mock_db()

    async with _app_client(user, db) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "csv"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    content = resp.text
    assert "Date" in content
    assert "Client" in content
    assert "Montant" in content


@pytest.mark.asyncio
async def test_export_csv_contains_transaction_rows():
    from app.main import app

    user = _make_user()
    order = SimpleNamespace(
        order_number="CMD-001",
        items=[SimpleNamespace(description="Produit A"), SimpleNamespace(description="Produit B")],
        client=SimpleNamespace(company_name="ACME SARL", full_name="Fallback Client"),
        subtotal_cents=10000,
        tax_cents=1925,
        total_cents=11925,
        payment_status="paid",
    )
    transaction = SimpleNamespace(
        order=order,
        transaction_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
        amount_cents=11925,
        status="success",
        method="cash",
    )
    db = _mock_db([transaction])

    async with _app_client(user, db) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "csv"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "CMD-001" in resp.text
    assert "ACME SARL" in resp.text
    assert "Produit A, Produit B" in resp.text
    assert "paid" in resp.text


@pytest.mark.asyncio
async def test_export_xlsx_contains_transaction_rows():
    from app.main import app

    user = _make_user()
    order = SimpleNamespace(
        order_number="CMD-002",
        items=[SimpleNamespace(description="Produit C")],
        client=SimpleNamespace(company_name="Beta SARL", full_name="Fallback Client"),
        subtotal_cents=5000,
        tax_cents=950,
        total_cents=5950,
        payment_status="paid",
    )
    transaction = SimpleNamespace(
        order=order,
        transaction_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
        amount_cents=5950,
        status="success",
        method="cash",
    )
    db = _mock_db([transaction])

    async with _app_client(user, db) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "xlsx"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_export_xlsx_returns_500_when_openpyxl_missing(monkeypatch):
    import builtins

    from app.main import app

    user = _make_user()
    db = _mock_db()

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "openpyxl":
            raise ImportError("no module named openpyxl")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    async with _app_client(user, db) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "xlsx"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_export_requires_organization_membership():
    from app.main import app

    user = _make_user()
    user.organization_id = None

    async with _app_client(user) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30", "format": "csv"},
        )

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_unauthenticated_returns_401():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get(
            "/api/v1/exports/journal-ventes",
            params={"start": "2026-01-01", "end": "2026-06-30"},
        )

    assert resp.status_code == 401
