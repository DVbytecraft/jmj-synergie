"""Unit tests for the Money value object."""
from __future__ import annotations

import pytest
from decimal import Decimal

from app.domain.value_objects.money import Money


class TestMoneyCreation:
    def test_valid_amount(self):
        m = Money(100, "XAF")
        assert m.cents == 100
        assert m.currency == "XAF"

    def test_zero_is_allowed(self):
        assert Money(0, "EUR").cents == 0

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            Money(-1, "XAF")

    def test_invalid_currency_raises(self):
        with pytest.raises(ValueError, match="ISO 4217"):
            Money(100, "US")

    def test_zero_factory(self):
        m = Money.zero("EUR")
        assert m.cents == 0
        assert m.currency == "EUR"

    def test_from_decimal(self):
        m = Money.from_decimal(Decimal("12.50"), "EUR")
        assert m.cents == 1250


class TestMoneyArithmetic:
    def test_add_same_currency(self):
        result = Money(100, "XAF") + Money(200, "XAF")
        assert result.cents == 300

    def test_add_different_currency_raises(self):
        with pytest.raises(ValueError, match="Currency mismatch"):
            Money(100, "XAF") + Money(100, "EUR")

    def test_sub_positive_result(self):
        result = Money(500, "EUR") - Money(200, "EUR")
        assert result.cents == 300

    def test_sub_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            Money(100, "EUR") - Money(200, "EUR")

    def test_multiply_by_int(self):
        result = Money(100, "XAF") * 3
        assert result.cents == 300

    def test_multiply_by_decimal(self):
        result = Money(100, "XAF") * Decimal("2.5")
        assert result.cents == 250

    def test_apply_rate_19_percent(self):
        m = Money(10000, "XAF")
        tax = m.apply_rate(Decimal("19"))
        assert tax.cents == 1900


class TestMoneyComparison:
    def test_lt(self):
        assert Money(100, "XAF") < Money(200, "XAF")

    def test_gt(self):
        assert Money(200, "XAF") > Money(100, "XAF")

    def test_le(self):
        assert Money(100, "XAF") <= Money(100, "XAF")
        assert Money(100, "XAF") <= Money(200, "XAF")

    def test_ge(self):
        assert Money(200, "XAF") >= Money(200, "XAF")
        assert Money(200, "XAF") >= Money(100, "XAF")

    def test_le_different_currency_raises(self):
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = Money(100, "XAF") <= Money(100, "EUR")

    def test_ge_different_currency_raises(self):
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = Money(100, "XAF") >= Money(100, "EUR")

    def test_eq(self):
        assert Money(100, "XAF") == Money(100, "XAF")

    def test_compare_different_currency_raises(self):
        with pytest.raises(ValueError):
            _ = Money(100, "XAF") < Money(100, "EUR")


class TestMoneyDisplay:
    def test_format_xaf(self):
        assert "XAF" in Money(500000, "XAF").format()

    def test_format_non_xaf(self):
        assert Money(1000, "EUR").format() == "10.00 EUR"

    def test_amount_property(self):
        assert Money(1000, "EUR").amount == Decimal("10.00")

    def test_is_zero(self):
        assert Money.zero().is_zero()
        assert not Money(1, "XAF").is_zero()
