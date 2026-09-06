from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.purchases import _set_totals, _supplier_dict, _validate_source_document
from app.infrastructure.database.models import PurchaseOrderItemModel, PurchaseOrderModel, SupplierModel


def _purchase() -> PurchaseOrderModel:
    row = PurchaseOrderModel(currency="XAF")
    row.items = [
        PurchaseOrderItemModel(description="Produit A", quantity=2, purchase_unit_price_cents=10_000),
        PurchaseOrderItemModel(description="Produit B", quantity=1, purchase_unit_price_cents=5_000),
    ]
    return row


def test_purchase_tax_is_optional() -> None:
    row = _purchase()
    _set_totals(row, apply_tax=False, tax_rate=Decimal("19.25"))
    assert row.subtotal_cents == 25_000
    assert row.tax_rate == 0
    assert row.tax_cents == 0
    assert row.total_cents == 25_000


def test_purchase_tax_is_applied_only_when_selected() -> None:
    row = _purchase()
    _set_totals(row, apply_tax=True, tax_rate=Decimal("20"))
    assert row.tax_cents == 5_000
    assert row.total_cents == 30_000


def test_supplier_response_keeps_shared_client_identity() -> None:
    client_id = uuid4()
    supplier = SupplierModel(
        id=uuid4(), code="FOU-1", name="Entreprise A", phone="699000000",
        client_id=client_id, currency="XAF", is_active=True,
    )
    supplier.created_at = SimpleNamespace(isoformat=lambda: "2026-09-06T00:00:00+00:00")
    result = _supplier_dict(supplier)
    assert result["client_id"] == str(client_id)


@pytest.mark.asyncio
async def test_scanned_source_document_can_be_linked_once() -> None:
    document_id = uuid4()
    organization_id = uuid4()
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[SimpleNamespace(id=document_id), None])
    await _validate_source_document(db, document_id, organization_id)
    assert db.scalar.await_count == 2


@pytest.mark.asyncio
async def test_unknown_source_document_is_rejected() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as error:
        await _validate_source_document(db, uuid4(), uuid4())
    assert error.value.status_code == 404
