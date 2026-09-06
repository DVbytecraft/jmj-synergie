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

    def test_add_item_to_in_production_before_fulfilment(self):
        order = _make_order()
        order.add_item(_make_item())
        actor = uuid.uuid4()
        order.confirm(actor)
        order.start_production(actor)
        order.add_item(_make_item())
        assert len(order.items) == 2

    def test_item_quantity_must_be_positive(self):
        with pytest.raises(ValueError):
            OrderItem(description="x", quantity=Decimal("0"), unit_price=Money(100, "XAF"))

    def test_item_empty_description_raises(self):
        with pytest.raises(ValueError, match="description"):
            OrderItem(description="  ", quantity=1, unit_price=Money(100, "XAF"))

    def test_item_delivered_quantity_out_of_bounds_raises(self):
        with pytest.raises(ValueError, match="delivered_quantity"):
            OrderItem(
                description="x", quantity=1, unit_price=Money(100, "XAF"),
                delivered_quantity=2,
            )

    def test_item_invoiced_quantity_out_of_bounds_raises(self):
        with pytest.raises(ValueError, match="invoiced_quantity"):
            OrderItem(
                description="x", quantity=5, unit_price=Money(100, "XAF"),
                delivered_quantity=2, invoiced_quantity=3,
            )

    def test_remove_item_not_found_raises(self):
        order = _make_order()
        order.add_item(_make_item())
        with pytest.raises(ValueError, match="not found"):
            order.remove_item(uuid.uuid4())

    def test_remove_item_from_draft(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        order.remove_item(item.id)
        assert not order.items

    def test_remove_item_from_confirmed_before_fulfilment(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.remove_item(item.id)
        assert not order.items

    def test_editing_items_after_delivery_starts_raises(self):
        order = _make_order()
        item = _make_item(qty=2)
        order.add_item(item)
        actor = uuid.uuid4()
        order.confirm(actor)
        order.record_delivery(actor, [(item.id, 1)])
        with pytest.raises(ValueError):
            order.add_item(_make_item())
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

    def test_zero_payment_raises(self):
        order = _make_order()
        order.add_item(_make_item())
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError, match="must be positive"):
            order.apply_payment(Money(0, "XAF"))

    def test_discount_reduces_total(self):
        order = _make_order()
        order.discount_cents = 10_000
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        assert order.discount.cents == 10_000
        assert order.total.cents == 90_000

    def test_shipping_added_to_delivered_total_when_fully_delivered(self):
        order = _make_order()
        order.shipping_cents = 5_000
        item = _make_item(price_cents=100_000, qty=Decimal("1"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.record_delivery(uuid.uuid4(), [(item.id, 1)])
        assert order.fully_delivered is True
        assert order.delivered_total.cents == 105_000

    def test_delivered_total_applies_discount_ratio_when_partial(self):
        order = _make_order()
        order.discount_cents = 10_000
        item = _make_item(price_cents=100_000, qty=Decimal("2"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.record_delivery(uuid.uuid4(), [(item.id, 1)])
        # delivered_subtotal=100000, ratio=0.5, discount applied=5000
        assert order.delivered_total.cents == 100_000 - 5_000

    def test_has_delivery_false_before_any_delivery(self):
        order = _make_order()
        order.add_item(_make_item())
        assert order.has_delivery is False

    def test_has_delivery_true_after_delivery(self):
        order = _make_order()
        item = _make_item(qty=Decimal("2"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.record_delivery(uuid.uuid4(), [(item.id, 1)])
        assert order.has_delivery is True

    def test_paid_and_refunded_properties(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(100_000, "XAF"))
        assert order.paid.cents == 100_000
        order.apply_refund(Money(40_000, "XAF"))
        assert order.refunded.cents == 40_000

    def test_is_fully_paid(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        assert order.is_fully_paid is False
        order.apply_payment(Money(100_000, "XAF"))
        assert order.is_fully_paid is True

    def test_days_overdue_computed_when_past_due_and_unpaid(self):
        from datetime import date, timedelta
        order = _make_order()
        order.due_date = date.today() - timedelta(days=5)
        assert order.days_overdue == 5

    def test_days_overdue_zero_when_no_due_date(self):
        order = _make_order()
        assert order.days_overdue == 0

    def test_refund_zero_amount_raises(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(100_000, "XAF"))
        with pytest.raises(ValueError, match="must be positive"):
            order.apply_refund(Money(0, "XAF"))

    def test_refund_exceeding_paid_raises(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(50_000, "XAF"))
        with pytest.raises(ValueError, match="exceeds paid"):
            order.apply_refund(Money(60_000, "XAF"))

    def test_full_refund_sets_refunded_status(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(100_000, "XAF"))
        order.apply_refund(Money(100_000, "XAF"))
        assert order.payment_status == PaymentStatus.REFUNDED

    def test_payment_status_overdue_after_full_refund_past_due(self):
        from datetime import date, timedelta
        order = _make_order()
        order.due_date = date.today() - timedelta(days=1)
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(50_000, "XAF"))
        order.apply_refund(Money(50_000, "XAF"))
        assert order.payment_status == PaymentStatus.OVERDUE

    def test_payment_status_pending_after_full_refund_no_due_date(self):
        order = _make_order()
        order.add_item(_make_item(price_cents=100_000, qty=Decimal("1")))
        order.confirm(uuid.uuid4())
        order.apply_payment(Money(50_000, "XAF"))
        order.apply_refund(Money(50_000, "XAF"))
        assert order.payment_status == PaymentStatus.PENDING


class TestOrderDelivery:
    def test_record_delivery_wrong_status_raises(self):
        order = _make_order()  # DRAFT
        order.add_item(_make_item())
        with pytest.raises(ValueError, match="Cannot record delivery"):
            order.record_delivery(uuid.uuid4(), [(order.items[0].id, 1)])

    def test_record_delivery_empty_list_raises(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError, match="At least one delivery"):
            order.record_delivery(uuid.uuid4(), [])

    def test_record_delivery_skips_non_positive_quantities(self):
        order = _make_order()
        item = _make_item(qty=Decimal("2"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.record_delivery(uuid.uuid4(), [(item.id, 0), (item.id, 1)])
        assert item.delivered_quantity == 1

    def test_record_delivery_item_not_found_raises(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError, match="not found"):
            order.record_delivery(uuid.uuid4(), [(uuid.uuid4(), 1)])

    def test_record_delivery_exceeds_ordered_quantity_raises(self):
        order = _make_order()
        item = _make_item(qty=Decimal("1"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError, match="exceeds ordered"):
            order.record_delivery(uuid.uuid4(), [(item.id, 5)])

    def test_record_delivery_no_positive_quantity_raises(self):
        order = _make_order()
        item = _make_item(qty=Decimal("1"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        with pytest.raises(ValueError, match="No positive delivered"):
            order.record_delivery(uuid.uuid4(), [(item.id, 0)])

    def test_record_delivery_partial_sets_partially_delivered(self):
        order = _make_order()
        item = _make_item(qty=Decimal("2"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.record_delivery(uuid.uuid4(), [(item.id, 1)])
        assert order.status == OrderStatus.PARTIALLY_DELIVERED

    def test_mark_delivered_quantities_invoiced(self):
        order = _make_order()
        item = _make_item(qty=Decimal("2"))
        order.add_item(item)
        order.confirm(uuid.uuid4())
        order.record_delivery(uuid.uuid4(), [(item.id, 2)])
        # First call invoices the pending quantity.
        total = order.mark_delivered_quantities_invoiced()
        assert total == 2
        # Second call: nothing pending, hits the "no pending" branch.
        total_again = order.mark_delivered_quantities_invoiced()
        assert total_again == 0

    def test_archive(self):
        order = _make_order()
        item = _make_item()
        order.add_item(item)
        actor = uuid.uuid4()
        order.confirm(actor)
        order.start_production(actor)
        order.mark_ready(actor)
        order.deliver(actor)
        order.archive(actor)
        assert order.status == OrderStatus.ARCHIVED
