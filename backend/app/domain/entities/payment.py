"""
PaymentTransaction entity — immutable once completed.
Refund entity with approval workflow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from app.domain.value_objects.money import Money


class PaymentMethod(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    CHECK = "check"
    CARD = "card"


class TransactionType(str, Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


@dataclass
class PaymentTransaction:
    """
    Represents one financial transaction.
    Once COMPLETED or REVERSED, it becomes immutable — never modify, only create corrections.
    """
    order_id: UUID
    client_id: UUID
    transaction_type: TransactionType
    method: PaymentMethod
    amount: Money
    recorded_by: UUID

    id: UUID = field(default_factory=uuid4)
    transaction_number: str = ""
    status: TransactionStatus = TransactionStatus.PENDING
    invoice_id: Optional[UUID] = None
    external_reference: Optional[str] = None
    receipt_number: Optional[str] = None
    bank_name: Optional[str] = None
    check_number: Optional[str] = None
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    transaction_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Domain operations ─────────────────────────────────────────────────────

    def complete(self, verified_by: Optional[UUID] = None) -> None:
        if self.status in (TransactionStatus.COMPLETED, TransactionStatus.REVERSED):
            raise ValueError(f"Transaction {self.transaction_number} already {self.status.value}")
        self.status = TransactionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def fail(self, reason: str) -> None:
        if self.status == TransactionStatus.COMPLETED:
            raise ValueError("Cannot fail a completed transaction — create a reversal")
        self.status = TransactionStatus.FAILED
        self.failure_reason = reason
        self.failed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_immutable(self) -> bool:
        return self.status in (TransactionStatus.COMPLETED, TransactionStatus.REVERSED)


class RefundStatus(str, Enum):
    REQUESTED = "requested"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RefundReason(str, Enum):
    PRODUCT_DEFECT = "product_defect"
    WRONG_ITEM = "wrong_item"
    NOT_DELIVERED = "not_delivered"
    CUSTOMER_REQUEST = "customer_request"
    DUPLICATE_PAYMENT = "duplicate_payment"
    BILLING_ERROR = "billing_error"
    OTHER = "other"


@dataclass
class Refund:
    """
    Refund request with approval workflow.
    Requires manager approval before money moves.
    """
    order_id: UUID
    client_id: UUID
    requested_amount: Money
    reason: RefundReason
    reason_detail: str
    requested_by: UUID
    original_transaction_id: UUID

    id: UUID = field(default_factory=uuid4)
    refund_number: str = ""
    status: RefundStatus = RefundStatus.REQUESTED
    approved_amount: Optional[Money] = None
    method: Optional[PaymentMethod] = None
    invoice_id: Optional[UUID] = None
    reviewed_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    refund_transaction_id: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Workflow ──────────────────────────────────────────────────────────────

    def submit_for_review(self, reviewer: UUID) -> None:
        if self.status != RefundStatus.REQUESTED:
            raise ValueError(f"Cannot review refund in status '{self.status.value}'")
        self.status = RefundStatus.UNDER_REVIEW
        self.reviewed_by = reviewer
        self.reviewed_at = datetime.now(timezone.utc)
        self._touch()

    def approve(self, approved_by: UUID, approved_amount: Optional[Money] = None) -> None:
        if self.status not in (RefundStatus.REQUESTED, RefundStatus.UNDER_REVIEW):
            raise ValueError(f"Cannot approve refund in status '{self.status.value}'")
        amount = approved_amount or self.requested_amount
        if amount.cents > self.requested_amount.cents:
            raise ValueError("Approved amount cannot exceed requested amount")
        self.approved_amount = amount
        self.approved_by = approved_by
        self.approved_at = datetime.now(timezone.utc)
        self.status = RefundStatus.APPROVED
        self._touch()

    def reject(self, rejected_by: UUID, reason: str) -> None:
        if self.status not in (RefundStatus.REQUESTED, RefundStatus.UNDER_REVIEW):
            raise ValueError(f"Cannot reject refund in status '{self.status.value}'")
        if not reason.strip():
            raise ValueError("Rejection reason is required")
        self.status = RefundStatus.REJECTED
        self.approved_by = rejected_by
        self.rejection_reason = reason
        self.rejected_at = datetime.now(timezone.utc)
        self._touch()

    def complete(self, transaction_id: UUID) -> None:
        if self.status != RefundStatus.APPROVED:
            raise ValueError("Refund must be approved before completing")
        self.status = RefundStatus.COMPLETED
        self.refund_transaction_id = transaction_id
        self.completed_at = datetime.now(timezone.utc)
        self._touch()

    def cancel(self) -> None:
        if self.status in (RefundStatus.COMPLETED, RefundStatus.REJECTED):
            raise ValueError(f"Cannot cancel refund in status '{self.status.value}'")
        self.status = RefundStatus.CANCELLED
        self._touch()

    @property
    def effective_amount(self) -> Money:
        return self.approved_amount or self.requested_amount

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
