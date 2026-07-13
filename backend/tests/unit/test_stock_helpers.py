from __future__ import annotations

from app.api.v1.endpoints.stock import _is_low_stock
from app.infrastructure.database.models import ProductModel


def _product(**overrides) -> ProductModel:
    p = ProductModel()
    p.track_stock = True
    p.low_stock_threshold = 10
    p.stock_quantity = 50
    for key, value in overrides.items():
        setattr(p, key, value)
    return p


def test_is_low_stock_false_when_tracking_disabled() -> None:
    assert _is_low_stock(_product(track_stock=False)) is False


def test_is_low_stock_false_when_no_threshold() -> None:
    assert _is_low_stock(_product(low_stock_threshold=None)) is False


def test_is_low_stock_true_when_quantity_at_or_below_threshold() -> None:
    assert _is_low_stock(_product(stock_quantity=10)) is True
    assert _is_low_stock(_product(stock_quantity=5)) is True


def test_is_low_stock_false_when_quantity_above_threshold() -> None:
    assert _is_low_stock(_product(stock_quantity=50)) is False


def test_is_low_stock_treats_null_quantity_as_zero() -> None:
    assert _is_low_stock(_product(stock_quantity=None)) is True
