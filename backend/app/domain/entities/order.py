"""
Order aggregate root — contains all business rules for order lifecycle.
Payment state machine lives here, not in the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from app.domain.value_objects.money import Money


class OrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    IN_PRODUCTION = "in_production"
    READY = "ready"
    PARTIALLY_DELIVERED = "partially_delivered"
    DELIVERED = "delivered"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    REFUNDED = "refunded"
    PARTIAL_REFUND = "partial_refund"


# Valid state transitions (FSM)
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.DRAFT:         {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED:     {OrderStatus.IN_PRODUCTION, OrderStatus.CANCELLED},
    OrderStatus.IN_PRODUCTION: {OrderStatus.READY, OrderStatus.CANCELLED, OrderStatus.DISPUTED},
    OrderStatus.READY:         {OrderStatus.PARTIALLY_DELIVERED, OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.PARTIALLY_DELIVERED: {OrderStatus.PARTIALLY_DELIVERED, OrderStatus.DELIVERED, OrderStatus.DISPUTED},
    OrderStatus.DELIVERED:     {OrderStatus.DISPUTED, OrderStatus.ARCHIVED},
    OrderStatus.DISPUTED:      {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.CANCELLED:     set(),
    OrderStatus.ARCHIVED:      set(),
}


@dataclass
class OrderItem:
    description: str
    quantity: int
    unit_price: Money
    unit: Optional[str] = None
    item_code: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0
    delivered_quantity: int = 0
    invoiced_quantity: int = 0
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if not self.description.strip():
            raise ValueError("description is required")
        if self.delivered_quantity < 0 or self.delivered_quantity > self.quantity:
            raise ValueError("delivered_quantity out of bounds")
        if self.invoiced_quantity < 0 or self.invoiced_quantity > self.delivered_quantity:
            raise ValueError("invoiced_quantity out of bounds")

    @property
    def line_total(self) -> Money:
        return self.unit_price * self.quantity

    @property
    def delivered_line_total(self) -> Money:
        return self.unit_price * self.delivered_quantity

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.delivered_quantity

    @property
    def invoiceable_quantity(self) -> int:
        return self.delivered_quantity - self.invoiced_quantity


@dataclass
class Order:
    """
    Order aggregate root.
    All mutations go through domain methods that enforce invariants.
    """
    client_id: UUID
    created_by: UUID
    organization_id: UUID
    currency: str = "XAF"

    # Financials
    tax_rate: Decimal = Decimal("0.00")
    discount_cents: int = 0
    shipping_cents: int = 0

    # Optional
    purchase_order_ref: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None

    # Identity
    id: UUID = field(default_factory=uuid4)
    order_number: str = ""
    status: OrderStatus = OrderStatus.DRAFT
    payment_status: PaymentStatus = PaymentStatus.PENDING

    # Internal tracking
    items: list[OrderItem] = field(default_factory=list)
    paid_cents: int = 0
    refunded_cents: int = 0
    confirmed_by: Optional[UUID] = None
    confirmed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[UUID] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[UUID] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Computed amounts ──────────────────────────────────────────────────────

    @property
    def subtotal(self) -> Money:
        return sum(
            (item.line_total for item in self.items),
            Money.zero(self.currency),
        )

    @property
    def tax_amount(self) -> Money:
        return self.subtotal.apply_rate(self.tax_rate)

    @property
    def discount(self) -> Money:
        return Money(self.discount_cents, self.currency)

    @property
    def shipping(self) -> Money:
        return Money(self.shipping_cents, self.currency)

    @property
    def total(self) -> Money:
        raw = self.subtotal + self.tax_amount + self.shipping
        if self.discount_cents > 0:
            raw = raw - self.discount
        return raw

    @property
    def delivered_subtotal(self) -> Money:
        return sum((item.delivered_line_total for item in self.items), Money.zero(self.currency))

    @property
    def delivered_tax_amount(self) -> Money:
        return self.delivered_subtotal.apply_rate(self.tax_rate)

    @property
    def delivered_total(self) -> Money:
        raw = self.delivered_subtotal + self.delivered_tax_amount
        if self.discount_cents > 0 and self.subtotal.cents > 0:
            delivered_ratio = self.delivered_subtotal.cents / self.subtotal.cents
            raw = raw - Money(int(self.discount_cents * delivered_ratio), self.currency)
        if self.shipping_cents > 0 and self.fully_delivered:
            raw = raw + self.shipping
        return raw

    @property
    def has_reliquat(self) -> bool:
        return any(item.remaining_quantity > 0 for item in self.items)

    @property
    def fully_delivered(self) -> bool:
        return bool(self.items) and all(item.remaining_quantity == 0 for item in self.items)

    @property
    def has_delivery(self) -> bool:
        return any(item.delivered_quantity > 0 for item in self.items)

    @property
    def paid(self) -> Money:
        return Money(self.paid_cents, self.currency)

    @property
    def refunded(self) -> Money:
        return Money(self.refunded_cents, self.currency)

    @property
    def balance_due(self) -> Money:
        due = self.total.cents - self.paid_cents + self.refunded_cents
        return Money(max(0, due), self.currency)

    @property
    def is_fully_paid(self) -> bool:
        return self.paid_cents >= self.total.cents

    @property
    def days_overdue(self) -> int:
        if self.due_date and self.payment_status not in (
            PaymentStatus.PAID, PaymentStatus.REFUNDED
        ):
            delta = (date.today() - self.due_date).days
            return max(0, delta)
        return 0

    # ── Item management ───────────────────────────────────────────────────────

    def add_item(self, item: OrderItem) -> None:
        if self.status not in (OrderStatus.DRAFT, OrderStatus.CONFIRMED):
            raise ValueError(f"Cannot add items when order is '{self.status.value}'")
        self.items.append(item)
        self._touch()

    def remove_item(self, item_id: UUID) -> None:
        if self.status != OrderStatus.DRAFT:
            raise ValueError("Items can only be removed from DRAFT orders")
        original = len(self.items)
        self.items = [i for i in self.items if i.id != item_id]
        if len(self.items) == original:
            raise ValueError(f"Item {item_id} not found in order")
        self._touch()

    # ── State machine ─────────────────────────────────────────────────────────

    def _transition_to(self, target: OrderStatus, actor: UUID) -> None:
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise ValueError(
                f"Transition {self.status.value} → {target.value} not allowed"
            )
        self.status = target
        self._touch()

    def confirm(self, confirmed_by: UUID) -> None:
        if not self.items:
            raise ValueError("Cannot confirm an order with no items")
        self._transition_to(OrderStatus.CONFIRMED, confirmed_by)
        self.confirmed_by = confirmed_by
        self.confirmed_at = datetime.now(timezone.utc)

    def start_production(self, actor: UUID) -> None:
        self._transition_to(OrderStatus.IN_PRODUCTION, actor)

    def mark_ready(self, actor: UUID) -> None:
        self._transition_to(OrderStatus.READY, actor)

    def deliver(self, actor: UUID) -> None:
        self._transition_to(OrderStatus.DELIVERED, actor)
        self.delivered_at = datetime.now(timezone.utc)

    def record_delivery(self, actor: UUID, deliveries: list[tuple[UUID, int]]) -> None:
        if self.status not in (
            OrderStatus.CONFIRMED,
            OrderStatus.IN_PRODUCTION,
            OrderStatus.READY,
            OrderStatus.PARTIALLY_DELIVERED,
        ):
            raise ValueError(f"Cannot record delivery when order is '{self.status.value}'")
        if not deliveries:
            raise ValueError("At least one delivery line is required")

        delivered_any = False
        for item_id, quantity in deliveries:
            if quantity <= 0:
                continue
            item = next((i for i in self.items if i.id == item_id), None)
            if item is None:
                raise ValueError(f"Item {item_id} not found in order")
            if item.delivered_quantity + quantity > item.quantity:
                raise ValueError("Delivered quantity exceeds ordered quantity")
            item.delivered_quantity += quantity
            delivered_any = True

        if not delivered_any:
            raise ValueError("No positive delivered quantity provided")

        if self.fully_delivered:
            self.status = OrderStatus.DELIVERED
            self.delivered_at = datetime.now(timezone.utc)
        else:
            self.status = OrderStatus.PARTIALLY_DELIVERED
        self._touch()

    def mark_delivered_quantities_invoiced(self) -> int:
        total_qty = 0
        for item in self.items:
            pending = item.invoiceable_quantity
            if pending > 0:
                item.invoiced_quantity += pending
                total_qty += pending
        self._touch()
        return total_qty

    def cancel(self, cancelled_by: UUID, reason: Optional[str] = None) -> None:
        self._transition_to(OrderStatus.CANCELLED, cancelled_by)
        self.cancelled_by = cancelled_by
        self.cancelled_at = datetime.now(timezone.utc)
        if reason:
            self.notes = f"[ANNULATION] {reason}\n{self.notes or ''}".strip()

    def archive(self, actor: UUID) -> None:
        self._transition_to(OrderStatus.ARCHIVED, actor)

    # ── Payment ───────────────────────────────────────────────────────────────

    def apply_payment(self, amount: Money) -> None:
        if self.status == OrderStatus.CANCELLED:
            raise ValueError("Cannot apply payment to a cancelled order")
        if amount.is_zero():
            raise ValueError("Payment amount must be positive")
        if amount.currency != self.currency:
            raise ValueError(f"Currency mismatch: {amount.currency} vs {self.currency}")
        self.paid_cents += amount.cents
        self._update_payment_status()
        self._touch()

    def apply_refund(self, amount: Money) -> None:
        if amount.is_zero():
            raise ValueError("Refund amount must be positive")
        if amount.cents > self.paid_cents:
            raise ValueError(
                f"Refund ({amount.cents}) exceeds paid ({self.paid_cents})"
            )
        self.refunded_cents += amount.cents
        self.paid_cents -= amount.cents
        self._update_payment_status()
        self._touch()

    def _update_payment_status(self) -> None:
        if self.refunded_cents >= self.total.cents:
            self.payment_status = PaymentStatus.REFUNDED
        elif self.paid_cents >= self.total.cents:
            self.payment_status = PaymentStatus.PAID
        elif self.paid_cents > 0 and self.refunded_cents > 0:
            self.payment_status = PaymentStatus.PARTIAL_REFUND
        elif self.paid_cents > 0:
            self.payment_status = PaymentStatus.PARTIAL
        elif self.due_date and date.today() > self.due_date:
            self.payment_status = PaymentStatus.OVERDUE
        else:
            self.payment_status = PaymentStatus.PENDING

    # ── Soft delete ───────────────────────────────────────────────────────────

    def soft_delete(self, deleted_by: UUID) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
