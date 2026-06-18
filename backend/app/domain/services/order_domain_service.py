"""
Order domain service — cross-entity business logic that doesn't belong to a single entity.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal

from app.domain.entities.order import Order, OrderItem, OrderStatus
from app.domain.value_objects.money import Money
from app.core.exceptions import (
    BusinessRuleError,
    InvalidOrderStateError,
    RefundExceedsPaidError,
)


class OrderDomainService:
    """Stateless domain service — no infrastructure dependencies."""

    @staticmethod
    def validate_can_be_invoiced(order: Order) -> None:
        if order.status not in (OrderStatus.CONFIRMED, OrderStatus.DELIVERED):
            raise InvalidOrderStateError(
                order.status.value, ["confirmed", "delivered"]
            )
        if not order.items:
            raise BusinessRuleError("Cannot invoice an order with no items")

    @staticmethod
    def validate_payment(order: Order, amount: Money) -> None:
        if order.status == OrderStatus.CANCELLED:
            raise InvalidOrderStateError(order.status.value, "active")
        if amount.is_zero():
            raise BusinessRuleError("Payment amount must be greater than zero")
        if amount.currency != order.currency:
            raise BusinessRuleError(
                f"Currency mismatch: payment is {amount.currency}, "
                f"order expects {order.currency}"
            )

    @staticmethod
    def validate_refund(order: Order, refund_amount: Money) -> None:
        if refund_amount.cents > order.paid_cents:
            raise RefundExceedsPaidError(refund_amount.cents, order.paid_cents)
        if refund_amount.is_zero():
            raise BusinessRuleError("Refund amount must be greater than zero")

    @staticmethod
    def compute_line_total(quantity: Decimal, unit_price_cents: int) -> Money:
        result = int(quantity * unit_price_cents)
        return Money(result)

    @staticmethod
    def check_credit_limit(
        current_balance_cents: int,
        new_order_total_cents: int,
        credit_limit_cents: int,
    ) -> bool:
        """Returns True if within credit limit (0 = unlimited)."""
        if credit_limit_cents == 0:
            return True
        return (current_balance_cents + new_order_total_cents) <= credit_limit_cents
