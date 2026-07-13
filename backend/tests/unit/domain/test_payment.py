"""Unit tests for the PaymentTransaction and Refund domain entities."""
from __future__ import annotations

import uuid

import pytest

from app.domain.entities.payment import (
    PaymentMethod,
    PaymentTransaction,
    Refund,
    RefundReason,
    RefundStatus,
    TransactionStatus,
    TransactionType,
)
from app.domain.value_objects.money import Money


def _make_transaction(**overrides) -> PaymentTransaction:
    defaults = dict(
        client_id=uuid.uuid4(),
        transaction_type=TransactionType.PAYMENT,
        method=PaymentMethod.CASH,
        amount=Money(10_000, "XAF"),
        recorded_by=uuid.uuid4(),
    )
    defaults.update(overrides)
    return PaymentTransaction(**defaults)


def _make_refund(**overrides) -> Refund:
    defaults = dict(
        order_id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        requested_amount=Money(10_000, "XAF"),
        reason=RefundReason.CUSTOMER_REQUEST,
        reason_detail="Client changed mind",
        requested_by=uuid.uuid4(),
        original_transaction_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return Refund(**defaults)


class TestPaymentTransaction:
    def test_complete(self):
        txn = _make_transaction()
        txn.complete()
        assert txn.status == TransactionStatus.COMPLETED
        assert txn.completed_at is not None

    def test_complete_already_completed_raises(self):
        txn = _make_transaction()
        txn.complete()
        with pytest.raises(ValueError, match="already"):
            txn.complete()

    def test_fail(self):
        txn = _make_transaction()
        txn.fail("card declined")
        assert txn.status == TransactionStatus.FAILED
        assert txn.failure_reason == "card declined"

    def test_fail_completed_raises(self):
        txn = _make_transaction()
        txn.complete()
        with pytest.raises(ValueError, match="reversal"):
            txn.fail("too late")

    def test_is_immutable(self):
        txn = _make_transaction()
        assert txn.is_immutable is False
        txn.complete()
        assert txn.is_immutable is True


class TestRefundWorkflow:
    def test_submit_for_review(self):
        refund = _make_refund()
        reviewer = uuid.uuid4()
        refund.submit_for_review(reviewer)
        assert refund.status == RefundStatus.UNDER_REVIEW
        assert refund.reviewed_by == reviewer

    def test_submit_for_review_wrong_status_raises(self):
        refund = _make_refund()
        refund.submit_for_review(uuid.uuid4())
        with pytest.raises(ValueError, match="Cannot review"):
            refund.submit_for_review(uuid.uuid4())

    def test_approve_full_amount(self):
        refund = _make_refund()
        approver = uuid.uuid4()
        refund.approve(approver)
        assert refund.status == RefundStatus.APPROVED
        assert refund.approved_amount == refund.requested_amount

    def test_approve_partial_amount(self):
        refund = _make_refund()
        refund.approve(uuid.uuid4(), Money(5_000, "XAF"))
        assert refund.approved_amount.cents == 5_000

    def test_approve_wrong_status_raises(self):
        refund = _make_refund()
        refund.approve(uuid.uuid4())
        with pytest.raises(ValueError, match="Cannot approve"):
            refund.approve(uuid.uuid4())

    def test_approve_amount_exceeds_requested_raises(self):
        refund = _make_refund()
        with pytest.raises(ValueError, match="exceed"):
            refund.approve(uuid.uuid4(), Money(20_000, "XAF"))

    def test_reject(self):
        refund = _make_refund()
        refund.reject(uuid.uuid4(), "Not eligible")
        assert refund.status == RefundStatus.REJECTED
        assert refund.rejection_reason == "Not eligible"

    def test_reject_wrong_status_raises(self):
        refund = _make_refund()
        refund.approve(uuid.uuid4())
        with pytest.raises(ValueError, match="Cannot reject"):
            refund.reject(uuid.uuid4(), "too late")

    def test_reject_empty_reason_raises(self):
        refund = _make_refund()
        with pytest.raises(ValueError, match="required"):
            refund.reject(uuid.uuid4(), "   ")

    def test_complete(self):
        refund = _make_refund()
        refund.approve(uuid.uuid4())
        txn_id = uuid.uuid4()
        refund.complete(txn_id)
        assert refund.status == RefundStatus.COMPLETED
        assert refund.refund_transaction_id == txn_id

    def test_complete_not_approved_raises(self):
        refund = _make_refund()
        with pytest.raises(ValueError, match="must be approved"):
            refund.complete(uuid.uuid4())

    def test_cancel(self):
        refund = _make_refund()
        refund.cancel()
        assert refund.status == RefundStatus.CANCELLED

    def test_cancel_completed_raises(self):
        refund = _make_refund()
        refund.approve(uuid.uuid4())
        refund.complete(uuid.uuid4())
        with pytest.raises(ValueError, match="Cannot cancel"):
            refund.cancel()

    def test_effective_amount_falls_back_to_requested(self):
        refund = _make_refund()
        assert refund.effective_amount == refund.requested_amount

    def test_effective_amount_uses_approved(self):
        refund = _make_refund()
        refund.approve(uuid.uuid4(), Money(5_000, "XAF"))
        assert refund.effective_amount.cents == 5_000
