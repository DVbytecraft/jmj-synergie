"""
Integration tests for /documents endpoints.
DB and external services are mocked so the suite stays fast and deterministic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORDER_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
DOC_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000001")


def _make_user(role: str = "manager", organization_id: uuid.UUID | None = ORG_ID) -> UserModel:
    user = UserModel()
    user.id = uuid.uuid4()
    user.organization_id = organization_id
    user.email = f"{role}@test.com"
    user.full_name = "Test User"
    user.role = role
    user.status = "active"
    user.is_deleted = False
    user.hashed_password = "x"
    user.refresh_token_jti = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = value if isinstance(value, list) else []
    return result


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


def _app_client(user: UserModel, db: AsyncMock | None = None):
    from app.main import app
    from app.api.v1.deps import get_current_user
    from app.api.v1.endpoints import documents
    from httpx import ASGITransport, AsyncClient

    if db is None:
        db = _mock_db()

    async def _db():
        yield db

    async def _user():
        return user

    app.dependency_overrides[documents.get_db] = _db
    app.dependency_overrides[get_current_user] = _user

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_list_documents_requires_organization():
    from app.main import app

    user = _make_user(organization_id=None)

    try:
        async with _app_client(user) as client:
            response = await client.get("/api/v1/documents")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_documents_returns_paginated_items_without_client_join():
    from app.main import app

    user = _make_user()
    db = _mock_db()
    document = SimpleNamespace(
        id=DOC_ID,
        document_type="invoice",
        document_number="FAC-001",
        file_name="invoice.pdf",
        is_signed=True,
        is_stamped=False,
        order_id=ORDER_ID,
        created_at=datetime.now(timezone.utc),
    )
    db.execute = AsyncMock(side_effect=[_mock_result(1), _mock_result([document])])

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/documents?document_type=invoice&skip=0&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["document_number"] == "FAC-001"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_documents_supports_date_range_filter():
    from app.main import app

    user = _make_user()
    db = _mock_db()
    document = SimpleNamespace(
        id=DOC_ID,
        document_type="invoice",
        document_number="FAC-002",
        file_name="invoice.pdf",
        is_signed=True,
        is_stamped=False,
        order_id=ORDER_ID,
        created_at=datetime.now(timezone.utc),
    )
    db.execute = AsyncMock(side_effect=[_mock_result(1), _mock_result([document])])

    try:
        async with _app_client(user, db) as client:
            response = await client.get(
                "/api/v1/documents?date_from=2026-01-01&date_to=2026-12-31"
            )
        assert response.status_code == 200
        assert response.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_documents_supports_client_type_join_filter():
    from app.main import app

    user = _make_user()
    db = _mock_db()
    document = SimpleNamespace(
        id=DOC_ID,
        document_type="quote",
        document_number="DEV-001",
        file_name="quote.pdf",
        is_signed=False,
        is_stamped=False,
        order_id=ORDER_ID,
        created_at=datetime.now(timezone.utc),
    )
    db.execute = AsyncMock(side_effect=[_mock_result(1), _mock_result([document])])

    try:
        async with _app_client(user, db) as client:
            response = await client.get("/api/v1/documents?client_type=company")
        assert response.status_code == 200
        assert response.json()["items"][0]["document_type"] == "quote"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_purchase_order_returns_201(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_purchase_order(self, order_id, created_by, db):
            assert order_id == ORDER_ID
            assert created_by == user.id
            assert db is not None
            return SimpleNamespace(id=DOC_ID, file_name="bc.pdf")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/purchase-order/{ORDER_ID}")
        assert response.status_code == 201
        assert response.json()["file_name"] == "bc.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_purchase_order_returns_400_on_validation_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_purchase_order(self, order_id, created_by, db):
            raise ValueError("invalid order")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/purchase-order/{ORDER_ID}")
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid order"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_purchase_order_returns_500_on_unexpected_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_purchase_order(self, order_id, created_by, db):
            raise RuntimeError("boom")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/purchase-order/{ORDER_ID}")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_pro_forma_returns_400_on_validation_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_pro_forma(self, order_id, created_by, db):
            raise ValueError("bad proforma")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/pro-forma/{ORDER_ID}")
        assert response.status_code == 400
        assert response.json()["detail"] == "bad proforma"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_pro_forma_returns_201_on_success(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_pro_forma(self, order_id, created_by, db):
            assert order_id == ORDER_ID
            assert created_by == user.id
            return SimpleNamespace(id=DOC_ID, file_name="pro-forma.pdf")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/pro-forma/{ORDER_ID}")
        assert response.status_code == 201
        assert response.json()["file_name"] == "pro-forma.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_pro_forma_returns_500_on_unexpected_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_pro_forma(self, order_id, created_by, db):
            raise RuntimeError("boom")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/pro-forma/{ORDER_ID}")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_delivery_note_returns_400_on_validation_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_delivery_note(self, **kwargs):
            raise ValueError("invalid delivery note")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/delivery-note/{ORDER_ID}")
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid delivery note"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_delivery_note_returns_500_on_unexpected_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_delivery_note(self, **kwargs):
            raise RuntimeError("nope")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/delivery-note/{ORDER_ID}")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_delivery_note_returns_201_on_success(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_delivery_note(self, **kwargs):
            assert kwargs["order_id"] == ORDER_ID
            assert kwargs["created_by"] == user.id
            return SimpleNamespace(id=DOC_ID, file_name="delivery.pdf")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/delivery-note/{ORDER_ID}")
        assert response.status_code == 201
        assert response.json()["file_name"] == "delivery.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_payment_receipt_returns_500_on_unexpected_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    payment_id = uuid.uuid4()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_payment_receipt(self, order_id, payment_id_arg, created_by, db):
            raise RuntimeError("boom")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/payment-receipt/{ORDER_ID}/{payment_id}")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_payment_receipt_returns_400_on_validation_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    payment_id = uuid.uuid4()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_payment_receipt(self, order_id, payment_id_arg, created_by, db):
            assert payment_id_arg == payment_id
            raise ValueError("payment missing")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/payment-receipt/{ORDER_ID}/{payment_id}")
        assert response.status_code == 400
        assert response.json()["detail"] == "payment missing"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_payment_receipt_returns_201_on_success(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    payment_id = uuid.uuid4()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_payment_receipt(self, order_id, payment_id_arg, created_by, db):
            assert order_id == ORDER_ID
            assert payment_id_arg == payment_id
            assert created_by == user.id
            return SimpleNamespace(id=DOC_ID, file_name="receipt.pdf")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/payment-receipt/{ORDER_ID}/{payment_id}")
        assert response.status_code == 201
        assert response.json()["file_name"] == "receipt.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_quote_pdf_returns_404_when_quote_missing():
    from app.main import app

    user = _make_user()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.post(f"/api/v1/documents/quote/{DOC_ID}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_quote_pdf_returns_201_on_success(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(SimpleNamespace(id=DOC_ID)))

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_quote(self, quote_id, created_by, db):
            assert quote_id == DOC_ID
            assert created_by == user.id
            return SimpleNamespace(id=DOC_ID, file_name="quote.pdf")

    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user, db) as client:
            response = await client.post(f"/api/v1/documents/quote/{DOC_ID}")
        assert response.status_code == 201
        assert response.json()["file_name"] == "quote.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_quote_pdf_returns_400_on_validation_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(SimpleNamespace(id=DOC_ID)))

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_quote(self, quote_id, created_by, db):
            raise ValueError("invalid quote")

    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user, db) as client:
            response = await client.post(f"/api/v1/documents/quote/{DOC_ID}")
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid quote"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_quote_pdf_returns_500_on_unexpected_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    db = _mock_db()
    db.execute = AsyncMock(return_value=_mock_result(SimpleNamespace(id=DOC_ID)))

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_quote(self, quote_id, created_by, db):
            raise RuntimeError("boom")

    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user, db) as client:
            response = await client.post(f"/api/v1/documents/quote/{DOC_ID}")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_invoice_returns_400_on_validation_error(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_invoice(self, order_id, created_by, db):
            raise ValueError("invalid invoice")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/invoice/{ORDER_ID}")
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid invoice"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_invoice_maps_unexpected_error_to_500(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_invoice(self, order_id, created_by, db):
            raise RuntimeError("boom")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/invoice/{ORDER_ID}")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_invoice_returns_201_on_success(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakePDFService:
        def __init__(self, _settings):
            pass

        async def generate_invoice(self, order_id, created_by, db):
            assert order_id == ORDER_ID
            assert created_by == user.id
            return SimpleNamespace(id=DOC_ID, file_name="invoice.pdf")

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=SimpleNamespace(id=ORDER_ID)))
    monkeypatch.setattr(documents, "PDFService", FakePDFService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/invoice/{ORDER_ID}")
        assert response.status_code == 201
        assert response.json()["file_name"] == "invoice.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_document_by_email_returns_404_when_user_missing(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    doc = SimpleNamespace(id=DOC_ID, created_by=user.id)
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

    db.execute = AsyncMock(return_value=_mock_result(None))
    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))

    try:
        async with _app_client(user, db) as client:
            response = await client.post(f"/api/v1/documents/{DOC_ID}/send-email", json={})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_document_by_email_forbidden_for_non_owner(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    doc = SimpleNamespace(id=DOC_ID, created_by=uuid.uuid4())
    order = SimpleNamespace(id=ORDER_ID, created_by=uuid.uuid4())

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))

    try:
        async with _app_client(user) as client:
            response = await client.post(
                f"/api/v1/documents/{DOC_ID}/send-email",
                json={"recipient_email": "client@example.com"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_document_by_email_returns_500_when_send_fails(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents
    from app.infrastructure.services.email import document_email_service

    user = _make_user("manager")
    db = _mock_db()
    doc = SimpleNamespace(id=DOC_ID, created_by=user.id)
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)
    stored_user = SimpleNamespace(id=user.id, email=user.email, full_name=user.full_name)
    issuer_profile = SimpleNamespace(user_id=user.id)

    class FakeService:
        async def send_document(self, **kwargs):
            return False

    db.execute = AsyncMock(side_effect=[_mock_result(stored_user), _mock_result(issuer_profile)])
    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
    monkeypatch.setattr(document_email_service, "DocumentEmailService", FakeService)

    try:
        async with _app_client(user, db) as client:
            response = await client.post(f"/api/v1/documents/{DOC_ID}/send-email", json={})
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_document_by_email_returns_200(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents
    from app.infrastructure.services.email import document_email_service

    user = _make_user("manager")
    db = _mock_db()
    doc = SimpleNamespace(id=DOC_ID, created_by=user.id)
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)
    stored_user = SimpleNamespace(id=user.id, email=user.email, full_name=user.full_name)
    issuer_profile = SimpleNamespace(user_id=user.id)

    class FakeService:
        async def send_document(self, **kwargs):
            assert kwargs["document"] is doc
            assert kwargs["user"] is stored_user
            assert kwargs["issuer_profile"] is issuer_profile
            assert kwargs["extra_recipient"] == "client@example.com"
            return True

    db.execute = AsyncMock(side_effect=[_mock_result(stored_user), _mock_result(issuer_profile)])
    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
    monkeypatch.setattr(document_email_service, "DocumentEmailService", FakeService)

    try:
        async with _app_client(user, db) as client:
            response = await client.post(
                f"/api/v1/documents/{DOC_ID}/send-email",
                json={"recipient_email": "client@example.com"},
            )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sign_document_forbidden_for_non_owner(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    doc = SimpleNamespace(id=DOC_ID, created_by=uuid.uuid4())
    order = SimpleNamespace(id=ORDER_ID, created_by=uuid.uuid4())

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/{DOC_ID}/sign")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sign_document_returns_200(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    doc = SimpleNamespace(id=DOC_ID, created_by=user.id)
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

    class FakeSignatureService:
        def __init__(self, _settings):
            pass

        async def sign_and_stamp(self, document_id, user_id, include_stamp, db):
            assert document_id == DOC_ID
            assert user_id == user.id
            assert include_stamp is True
            return "/tmp/signed.pdf"

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
    monkeypatch.setattr(documents, "SignatureService", FakeSignatureService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/{DOC_ID}/sign")
        assert response.status_code == 200
        assert response.json()["signed_path"] == "/tmp/signed.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sign_document_maps_error_to_500(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    doc = SimpleNamespace(id=DOC_ID, created_by=user.id)
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

    class FakeSignatureService:
        def __init__(self, _settings):
            pass

        async def sign_and_stamp(self, document_id, user_id, include_stamp, db):
            raise RuntimeError("broken")

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
    monkeypatch.setattr(documents, "SignatureService", FakeSignatureService)

    try:
        async with _app_client(user) as client:
            response = await client.post(f"/api/v1/documents/{DOC_ID}/sign")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_rejects_unknown_file_type():
    from app.main import app

    user = _make_user()

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/documents/scan-invoice",
                files={"file": ("invoice.txt", b"not-a-pdf", "text/plain")},
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_rejects_file_too_large(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    monkeypatch.setattr(type(documents.settings), "max_file_size_bytes", property(lambda self: 3), raising=False)
    monkeypatch.setattr(documents.settings, "MAX_FILE_SIZE_MB", 0)

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/documents/scan-invoice",
                files={"file": ("invoice.pdf", b"%PDF-1.7 body", "application/pdf")},
            )
        assert response.status_code == 413
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_validates_order_when_provided(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()
    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(side_effect=HTTPException(status_code=404, detail="Commande introuvable")))

    try:
        async with _app_client(user) as client:
            response = await client.post(
                f"/api/v1/documents/scan-invoice?order_id={ORDER_ID}",
                files={"file": ("invoice.pdf", b"%PDF-1.7 body", "application/pdf")},
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_maps_memory_error_to_503(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakeOCRService:
        def __init__(self, _settings):
            pass

        async def scan_invoice(self, file, order_id, user_id, db):
            raise MemoryError()

    monkeypatch.setattr(documents, "OCRService", FakeOCRService)

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/documents/scan-invoice",
                files={"file": ("invoice.pdf", b"%PDF-1.7 body", "application/pdf")},
            )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_passes_http_exception_through(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakeOCRService:
        def __init__(self, _settings):
            pass

        async def scan_invoice(self, file, order_id, user_id, db):
            raise HTTPException(status_code=415, detail="forced")

    monkeypatch.setattr(documents, "OCRService", FakeOCRService)

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/documents/scan-invoice",
                files={"file": ("invoice.pdf", b"%PDF-1.7 body", "application/pdf")},
            )
        assert response.status_code == 415
        assert response.json()["detail"] == "forced"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_maps_generic_error_to_500(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakeOCRService:
        def __init__(self, _settings):
            pass

        async def scan_invoice(self, file, order_id, user_id, db):
            raise RuntimeError("ocr fail")

    monkeypatch.setattr(documents, "OCRService", FakeOCRService)

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/documents/scan-invoice",
                files={"file": ("invoice.pdf", b"%PDF-1.7 body", "application/pdf")},
            )
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scan_invoice_returns_201_on_success(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user()

    class FakeOCRService:
        def __init__(self, _settings):
            pass

        async def scan_invoice(self, file, order_id, user_id, db):
            return {
                "document_id": str(DOC_ID),
                "order_id": str(ORDER_ID),
                "extracted_data": {"total": 1000},
                "confidence": 0.91,
                "raw_text": "facture",
            }

    monkeypatch.setattr(documents, "OCRService", FakeOCRService)

    try:
        async with _app_client(user) as client:
            response = await client.post(
                "/api/v1/documents/scan-invoice",
                files={"file": ("invoice.pdf", b"%PDF-1.7 body", "application/pdf")},
            )
        assert response.status_code == 201
        assert response.json()["confidence"] == 0.91
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_forbidden_for_non_owner(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    doc = SimpleNamespace(id=DOC_ID, created_by=uuid.uuid4(), last_emailed_at=None)
    order = SimpleNamespace(id=ORDER_ID, created_by=uuid.uuid4())

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))

    try:
        async with _app_client(user) as client:
            response = await client.get(f"/api/v1/documents/{DOC_ID}/download")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_redirects_remote_file(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    doc = SimpleNamespace(
        id=DOC_ID,
        created_by=user.id,
        file_path="https://cdn.example.com/doc.pdf",
        file_name="doc.pdf",
        mime_type="application/pdf",
        last_emailed_at=None,
    )
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)
    issuer_profile = SimpleNamespace(auto_send_documents=False)

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
    db.execute = AsyncMock(return_value=_mock_result(issuer_profile))

    try:
        async with _app_client(user, db) as client:
            response = await client.get(
                f"/api/v1/documents/{DOC_ID}/download",
                follow_redirects=False,
            )
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "https://cdn.example.com/doc.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_marks_first_download_and_schedules_email(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    issuer_profile = SimpleNamespace(auto_send_documents=True)

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 test")
        doc = SimpleNamespace(
            id=DOC_ID,
            created_by=user.id,
            file_path=str(file_path),
            file_name="doc.pdf",
            mime_type="application/pdf",
            last_emailed_at=None,
        )
        order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

        monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
        monkeypatch.setattr(documents.settings, "STORAGE_PATH", tmp)
        db.execute = AsyncMock(return_value=_mock_result(issuer_profile))

        try:
            async with _app_client(user, db) as client:
                response = await client.get(f"/api/v1/documents/{DOC_ID}/download")
            assert response.status_code == 200
            assert doc.last_emailed_at is not None
            db.flush.assert_awaited()
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_skips_email_when_already_sent(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    issuer_profile = SimpleNamespace(auto_send_documents=True)

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 test")
        already_emailed = datetime.now(timezone.utc)
        doc = SimpleNamespace(
            id=DOC_ID,
            created_by=user.id,
            file_path=str(file_path),
            file_name="doc.pdf",
            mime_type="application/pdf",
            last_emailed_at=already_emailed,
        )
        order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

        monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
        monkeypatch.setattr(documents.settings, "STORAGE_PATH", tmp)
        db.execute = AsyncMock(return_value=_mock_result(issuer_profile))

        try:
            async with _app_client(user, db) as client:
                response = await client.get(f"/api/v1/documents/{DOC_ID}/download")
            assert response.status_code == 200
            assert doc.last_emailed_at is already_emailed
            db.flush.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_rejects_path_outside_storage(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    doc = SimpleNamespace(
        id=DOC_ID,
        created_by=user.id,
        file_path="C:\\Windows\\system32\\secret.pdf",
        file_name="doc.pdf",
        mime_type="application/pdf",
        last_emailed_at=None,
    )
    order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

    monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
    db.execute = AsyncMock(return_value=_mock_result(None))

    try:
        async with _app_client(user, db) as client:
            response = await client.get(f"/api/v1/documents/{DOC_ID}/download")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_returns_404_when_file_missing(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    issuer_profile = SimpleNamespace(auto_send_documents=False)

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "missing.pdf"
        doc = SimpleNamespace(
            id=DOC_ID,
            created_by=user.id,
            file_path=str(file_path),
            file_name="missing.pdf",
            mime_type="application/pdf",
            last_emailed_at=None,
        )
        order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

        monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
        monkeypatch.setattr(documents.settings, "STORAGE_PATH", tmp)
        db.execute = AsyncMock(return_value=_mock_result(issuer_profile))

        try:
            async with _app_client(user, db) as client:
                response = await client.get(f"/api/v1/documents/{DOC_ID}/download")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_document_returns_file_response_for_local_file(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    db = _mock_db()
    issuer_profile = SimpleNamespace(auto_send_documents=False)

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 test")
        doc = SimpleNamespace(
            id=DOC_ID,
            created_by=user.id,
            file_path=str(file_path),
            file_name="doc.pdf",
            mime_type="application/pdf",
            last_emailed_at=None,
        )
        order = SimpleNamespace(id=ORDER_ID, created_by=user.id)

        monkeypatch.setattr(documents, "_get_document_with_order", AsyncMock(return_value=(doc, order)))
        monkeypatch.setattr(documents.settings, "STORAGE_PATH", tmp)
        db.execute = AsyncMock(return_value=_mock_result(issuer_profile))

        try:
            async with _app_client(user, db) as client:
                response = await client.get(f"/api/v1/documents/{DOC_ID}/download")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_order_documents_forbidden_for_non_owner(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("manager")
    order = SimpleNamespace(id=ORDER_ID, created_by=uuid.uuid4())

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=order))

    try:
        async with _app_client(user) as client:
            response = await client.get(f"/api/v1/documents/orders/{ORDER_ID}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_order_documents_returns_items_for_admin(monkeypatch):
    from app.main import app
    from app.api.v1.endpoints import documents

    user = _make_user("admin")
    db = _mock_db()
    order = SimpleNamespace(id=ORDER_ID, created_by=uuid.uuid4())
    document = SimpleNamespace(
        id=DOC_ID,
        document_type="invoice",
        document_number="FAC-001",
        file_name="invoice.pdf",
        is_signed=True,
        is_stamped=False,
        created_at=datetime.now(timezone.utc),
    )

    monkeypatch.setattr(documents, "_get_order_or_404", AsyncMock(return_value=order))
    db.execute = AsyncMock(return_value=_mock_result([document]))

    try:
        async with _app_client(user, db) as client:
            response = await client.get(f"/api/v1/documents/orders/{ORDER_ID}")
        assert response.status_code == 200
        assert response.json()[0]["document_number"] == "FAC-001"
    finally:
        app.dependency_overrides.clear()
