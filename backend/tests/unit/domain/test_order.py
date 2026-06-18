"""Unit tests for Order aggregate root — state machine and invariants."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.domain.entities.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.domain.value_objects.money import Money


def _make_order() -> Order:
    return Order(
        client_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        currency="XAF",
    )


def _make_item(price_cents: int = 100_000, qty: Decimal = Decimal("2")) -> OrderItem:
    return OrderItem(
        description="Tee-shirt personnalisé",
        quantity=qty,
        unit_price=Money(price_cents, "XAF"),
    )


class TestOrderItems:
    def test_add_item_to_draft(self):
        order = _make_order()
        order.add_item(_make_item())
        assert len(order.items) == 1

    def test_add_item_to_confirmed(self):
        order = _make_order()
        order.add_item(_make_item())
        order.confirm(uuid.uuid4())
        order.add_item(_make_item())
        assert len(order.items) == 2

    def test_add_item_to_in_production_raises(self):
        order = _make_order()
        order.add_item(_make_item())
        actor = uuid.uuid4()
        order.confirm(actor)
        order.start_production(actor)
        with pytest.raises(ValueError):
            order.add_item(_make_item())

    def test_item_quantity_must_be_positive(self):
        with pytest.raises(ValueError):
            OrderItem(description="x", quantity=Decimal("0"), unit_price=Money(100, "XAF"))

    def test_remove_item_from_draft(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        order.remove_item(item.id)
        assert not order.items

    def test_remove_item_from_confirmed_raises(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError):
            order.remove_item(item.id)


class TestOrderStateMachine:
    def test_confirm_with_items(self):
        order = _make_order()
        order.add_item(_make_item())
        order.confirm(uuid.uuid4())
        assert order.status == OrderStatus.CONFIRMED

    def test_confirm_empty_order_raises(self):
        order = _make_order()
        with pytest.raises(ValueError, match="no items"):
            order.confirm(uuid.uuid4())

    def test_invalid_transition_raises(self):
        order = _make_order()  # DRAFT
        with pytest.raises(ValueError, match="not allowed"):
            order.deliver(uuid.uuid4())

    def test_full_lifecycle(self):
        order = _make_order()
        actor = uuid.uuid4()
        order.add_item(_make_item())
        order.confirm(actor)
        order.start_production(actor)
        order.mark_ready(actor)
        order.deliver(actor)
        assert order.status == OrderStatus.DELIVERED
        assert order.delivered_at is not None

    def test_cancel_confirmed_order(self):
        order = _make_order()
        actor = uuid.uuid4()
        order.add_item(_make_item())
        order.confirm(actor)
        order.cancel(actor, reason="Client a annulé")
        assert order.status == OrderStatus.CANCELLED
        assert "ANNULATION" in (order.notes or "")

    def test_cancelled_order_cannot_be_confirmed_again(self):
        order = _make_order()
        actor = uuid.uuid4()
        order.add_item(_make_item())
        order.confirm(actor)
        order.cancel(actor)
        with pytest.raises(ValueError, match="not allowed"):
            order.confirm(actor)


class TestOrderFinancials:
    def test_subtotal_is_sum_of_lines(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("2")))
        order.add_item(_make_item(price_cents=50_000, qty=Decimal("3")))
        # 2×100000 + 3×50000 = 350000
        assert order.subtotal.cents == 350_000

    def test_total_includes_tax(self):
        order = _make_order()
        order.tax_rate = Decimal("19")
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        # subtotal=100000, tax=19000, total=119000
        assert order.total.cents == 119_000

    def test_apply_payment_updates_paid(self):
        order = _make_order()
        order.add_item(_make_item())
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(100_000, "XAF"))
        assert order.paid_cents == 100_000

    def test_full_payment_sets_paid_status(self):
        order = _make_order()
        item = _make_item(price_cents=100_000, qty=Decimal("1"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(100_000, "XAF"))
        assert order.payment_status == PaymentStatus.PAID

    def test_partial_payment_sets_partial_status(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(50_000, "XAF"))
        assert order.payment_status == PaymentStatus.PARTIAL

    def test_payment_on_cancelled_order_raises(self):
        order = _make_order()
        actor = uuid.uuid4()
        order.add_item(_make_item())
        order.confirm(actor)
        order.cancel(actor)
        with pytest.raises(ValueError, match="cancelled"):
            order.apply_payment(Money(1000, "XAF"))

    def test_payment_currency_mismatch_raises(self):
        order = _make_order()
        order.add_item(_make_item())
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError, match="Currency mismatch"):
            order.apply_payment(Money(1000, "EUR"))
