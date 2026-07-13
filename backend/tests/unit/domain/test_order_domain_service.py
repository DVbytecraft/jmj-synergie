from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.core.exceptions import BusinessRuleError, InvalidOrderStateError, RefundExceedsPaidError
from app.domain.entities.order import Order, OrderItem, OrderStatus
from app.domain.services.order_domain_service import OrderDomainService
from app.domain.value_objects.money import Money


def make_order(
    *,
    status: OrderStatus = OrderStatus.CONFIRMED,
    with_item: bool = True,
    currency: str = "XAF",
) -> Order:
    order = Order(
        client_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        currency=currency,
        tax_rate=Decimal("0"),
        order_number="CMD-100",
        status=status,
    )
    if with_item:
        order.items.append(
            OrderItem(
                description="Pave",
                quantity=2,
                unit_price=Money(5000, currency),
            )
        )
    return order


def test_validate_can_be_invoiced_accepts_confirmed_and_delivered_orders() -> None:
    OrderDomainService.validate_can_be_invoiced(make_order(status=OrderStatus.CONFIRMED))
    OrderDomainService.validate_can_be_invoiced(make_order(status=OrderStatus.DELIVERED))


def test_validate_can_be_invoiced_rejects_invalid_status_and_empty_items() -> None:
    with pytest.raises(InvalidOrderStateError):
        OrderDomainService.validate_can_be_invoiced(make_order(status=OrderStatus.DRAFT))

    with pytest.raises(BusinessRuleError, match="no items"):
        OrderDomainService.validate_can_be_invoiced(
            make_order(status=OrderStatus.CONFIRMED, with_item=False)
        )


def test_validate_payment_rejects_invalid_order_states() -> None:
    with pytest.raises(InvalidOrderStateError):
        OrderDomainService.validate_payment(
            make_order(status=OrderStatus.CANCELLED),
            Money(1000, "XAF"),
        )

    with pytest.raises(InvalidOrderStateError):
        OrderDomainService.validate_payment(
            make_order(status=OrderStatus.DRAFT),
            Money(1000, "XAF"),
        )


def test_validate_payment_rejects_zero_mismatch_already_paid_and_overpay() -> None:
    order = make_order()

    with pytest.raises(BusinessRuleError, match="greater than zero"):
        OrderDomainService.validate_payment(order, Money.zero("XAF"))

    with pytest.raises(BusinessRuleError, match="Currency mismatch"):
        OrderDomainService.validate_payment(order, Money(1000, "EUR"))

    order.paid_cents = order.total.cents
    with pytest.raises(BusinessRuleError, match="enti"):
        OrderDomainService.validate_payment(order, Money(1000, "XAF"))

    order.paid_cents = 9000
    with pytest.raises(BusinessRuleError, match="d.passe le solde restant"):
        OrderDomainService.validate_payment(order, Money(2000, "XAF"))


def test_validate_payment_accepts_valid_partial_payment() -> None:
    order = make_order()
    order.paid_cents = 1000

    OrderDomainService.validate_payment(order, Money(2000, "XAF"))


def test_validate_refund_rejects_excess_and_zero_amounts() -> None:
    order = make_order()
    order.paid_cents = 5000

    with pytest.raises(RefundExceedsPaidError):
        OrderDomainService.validate_refund(order, Money(6000, "XAF"))

    with pytest.raises(BusinessRuleError, match="greater than zero"):
        OrderDomainService.validate_refund(order, Money.zero("XAF"))


def test_validate_refund_accepts_valid_amount() -> None:
    order = make_order()
    order.paid_cents = 5000

    OrderDomainService.validate_refund(order, Money(3000, "XAF"))


def test_compute_line_total_rounds_and_returns_money() -> None:
    total = OrderDomainService.compute_line_total(Decimal("2.5"), 399)

    assert total.cents == 997
    assert total.currency == "XAF"


def test_check_credit_limit_handles_unlimited_and_thresholds() -> None:
    assert OrderDomainService.check_credit_limit(1000, 5000, 0) is True
    assert OrderDomainService.check_credit_limit(1000, 4000, 5000) is True
    assert OrderDomainService.check_credit_limit(1000, 5000, 5000) is False
