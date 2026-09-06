from decimal import Decimal

from app.api.v1.endpoints.purchases import _set_totals
from app.infrastructure.database.models import PurchaseOrderItemModel, PurchaseOrderModel


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
