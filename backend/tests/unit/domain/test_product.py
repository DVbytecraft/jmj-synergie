"""Unit tests for the Product domain entity — validation and lifecycle."""
from __future__ import annotations

import uuid

import pytest

from app.domain.entities.product import Product, ProductStatus


def _make_product(**overrides) -> Product:
    defaults = dict(
        name="Ciment Portland",
        unit_price_cents=500_000,
        created_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return Product(**defaults)


class TestProductValidation:
    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            _make_product(name="  ")

    def test_negative_price_raises(self):
        with pytest.raises(ValueError, match="unit_price_cents"):
            _make_product(unit_price_cents=-1)

    def test_invalid_tax_rate_raises(self):
        with pytest.raises(ValueError, match="tax_rate"):
            _make_product(tax_rate=150)

    def test_invalid_min_order_quantity_raises(self):
        with pytest.raises(ValueError, match="min_order_quantity"):
            _make_product(min_order_quantity=0)


class TestProductUpdate:
    def test_update_all_fields(self):
        product = _make_product()
        product.update(
            name="New name",
            description="desc",
            short_description="short",
            category="cat",
            unit="kg",
            unit_price_cents=1000,
            tax_rate=19,
            min_order_quantity=2,
            notes="notes",
            supplier_ref="SUP-1",
        )
        assert product.name == "New name"
        assert product.description == "desc"
        assert product.short_description == "short"
        assert product.category == "cat"
        assert product.unit == "kg"
        assert product.unit_price_cents == 1000
        assert product.tax_rate == 19
        assert product.min_order_quantity == 2
        assert product.notes == "notes"
        assert product.supplier_ref == "SUP-1"

    def test_update_noop(self):
        product = _make_product()
        original = product.name
        product.update()
        assert product.name == original


class TestProductLifecycle:
    def test_activate(self):
        product = _make_product()
        product.deactivate()
        product.activate()
        assert product.status == ProductStatus.ACTIVE

    def test_activate_deleted_raises(self):
        product = _make_product()
        product.soft_delete(uuid.uuid4())
        with pytest.raises(ValueError, match="supprimé"):
            product.activate()

    def test_deactivate(self):
        product = _make_product()
        product.deactivate()
        assert product.status == ProductStatus.INACTIVE

    def test_deactivate_discontinued_raises(self):
        product = _make_product()
        product.discontinue()
        with pytest.raises(ValueError, match="arrêté"):
            product.deactivate()

    def test_discontinue(self):
        product = _make_product()
        product.discontinue()
        assert product.status == ProductStatus.DISCONTINUED

    def test_soft_delete(self):
        product = _make_product()
        product.soft_delete(uuid.uuid4())
        assert product.is_deleted is True
        assert product.status == ProductStatus.INACTIVE


class TestProductStock:
    def test_adjust_stock_requires_tracking(self):
        product = _make_product(track_stock=False)
        with pytest.raises(ValueError, match="inventaire"):
            product.adjust_stock(5)

    def test_adjust_stock_increases_quantity(self):
        product = _make_product(track_stock=True, stock_quantity=10)
        product.adjust_stock(5)
        assert product.stock_quantity == 15

    def test_adjust_stock_insufficient_raises(self):
        product = _make_product(track_stock=True, stock_quantity=5)
        with pytest.raises(ValueError, match="insuffisant"):
            product.adjust_stock(-10)

    def test_is_low_stock_false_without_tracking(self):
        product = _make_product(track_stock=False)
        assert product.is_low_stock is False

    def test_is_low_stock_true(self):
        product = _make_product(track_stock=True, stock_quantity=2, low_stock_threshold=5)
        assert product.is_low_stock is True

    def test_is_available(self):
        product = _make_product()
        assert product.is_available is True
        product.deactivate()
        assert product.is_available is False

    def test_unit_price_tax_included(self):
        product = _make_product(unit_price_cents=1000, tax_rate=19)
        assert product.unit_price_tax_included_cents == 1190
