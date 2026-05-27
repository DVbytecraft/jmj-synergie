"""SQLAlchemy implementation of IPaymentRepository & IRefundRepository."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.payment import (
    PaymentTransaction, TransactionType, PaymentMethod, TransactionStatus,
    Refund, RefundReason, RefundStatus,
)
from app.domain.repositories.i_payment_repository import IPaymentRepository, IRefundRepository
from app.domain.value_objects.money import Money
from app.infrastructure.database.models import PaymentTransactionModel, RefundModel


class PaymentRepository(IPaymentRepository):

    def __init__(self, session: AsyncSession, org_id: UUID | None = None) -> None:
        self._s = session
        self._org_id = org_id

    async def get_by_id(self, txn_id: UUID) -> PaymentTransaction | None:
        q = select(PaymentTransactionModel).where(PaymentTransactionModel.id == txn_id)
        if self._org_id is not None:
            q = q.where(PaymentTransactionModel.organization_id == self._org_id)
        row = (await self._s.execute(q)).scalar_one_or_none()
        return _txn_to_entity(row) if row else None

    async def list_by_order(self, order_id: UUID) -> list[PaymentTransaction]:
        q = (
            select(PaymentTransactionModel)
            .where(PaymentTransactionModel.order_id == order_id)
            .order_by(PaymentTransactionModel.transaction_date.desc())
        )
        if self._org_id is not None:
            q = q.where(PaymentTransactionModel.organization_id == self._org_id)
        rows = (await self._s.execute(q)).scalars().all()
        return [_txn_to_entity(r) for r in rows]

    async def list_by_client(self, client_id: UUID, skip: int, limit: int) -> tuple[list[PaymentTransaction], int]:
        q = select(PaymentTransactionModel).where(PaymentTransactionModel.client_id == client_id)
        if self._org_id is not None:
            q = q.where(PaymentTransactionModel.organization_id == self._org_id)
        total = (await self._s.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await self._s.execute(
            q.order_by(PaymentTransactionModel.transaction_date.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return [_txn_to_entity(r) for r in rows], total

    async def save(self, txn: PaymentTransaction) -> PaymentTransaction:
        row = await self._s.get(PaymentTransactionModel, txn.id)
        if row is None:
            row = PaymentTransactionModel()
            self._s.add(row)
        _copy_txn(txn, row)
        if self._org_id is not None and row.organization_id is None:
            row.organization_id = self._org_id
        await self._s.flush()
        await self._s.refresh(row)
        return _txn_to_entity(row)

    async def generate_number(self) -> str:
        now = datetime.now(timezone.utc)
        prefix = f"TXN-{now.strftime('%Y%m%d')}"
        suffix = secrets.token_hex(4).upper()
        return f"{prefix}-{suffix}"


class RefundRepository(IRefundRepository):

    def __init__(self, session: AsyncSession, org_id: UUID | None = None) -> None:
        self._s = session
        self._org_id = org_id

    async def get_by_id(self, refund_id: UUID) -> Refund | None:
        q = select(RefundModel).where(RefundModel.id == refund_id)
        if self._org_id is not None:
            q = q.where(RefundModel.organization_id == self._org_id)
        row = (await self._s.execute(q)).scalar_one_or_none()
        return _refund_to_entity(row) if row else None

    async def list_by_order(self, order_id: UUID) -> list[Refund]:
        q = select(RefundModel).where(RefundModel.order_id == order_id)
        if self._org_id is not None:
            q = q.where(RefundModel.organization_id == self._org_id)
        rows = (await self._s.execute(q)).scalars().all()
        return [_refund_to_entity(r) for r in rows]

    async def list(self, skip: int, limit: int, status: str | None) -> tuple[list[Refund], int]:
        q = select(RefundModel)
        if self._org_id is not None:
            q = q.where(RefundModel.organization_id == self._org_id)
        if status:
            q = q.where(RefundModel.status == status)
        total = (await self._s.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await self._s.execute(
            q.order_by(RefundModel.requested_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return [_refund_to_entity(r) for r in rows], total

    async def save(self, refund: Refund) -> Refund:
        row = await self._s.get(RefundModel, refund.id)
        if row is None:
            row = RefundModel()
            self._s.add(row)
        _copy_refund(refund, row)
        if self._org_id is not None and row.organization_id is None:
            row.organization_id = self._org_id
        await self._s.flush()
        await self._s.refresh(row)
        return _refund_to_entity(row)

    async def generate_number(self) -> str:
        import sqlalchemy as sa
        now = datetime.now(timezone.utc)
        result = await self._s.execute(sa.text("SELECT nextval('seq_refund_number')"))
        seq = result.scalar_one()
        return f"RMB-{now.strftime('%Y%m')}-{seq:04d}"


# ── Mappers ────────────────────────────────────────────────────────────────────

def _txn_to_entity(row: PaymentTransactionModel) -> PaymentTransaction:
    return PaymentTransaction(
        id=row.id,
        transaction_number=row.transaction_number,
        order_id=row.order_id,
        client_id=row.client_id,
        transaction_type=TransactionType(row.transaction_type),
        method=PaymentMethod(row.method),
        amount=Money(row.amount_cents, row.currency),
        recorded_by=row.recorded_by,
        status=TransactionStatus(row.status),
        external_reference=row.external_reference,
        bank_name=row.bank_name,
        check_number=row.check_number,
        notes=row.notes,
        failure_reason=row.failure_reason,
        completed_at=row.completed_at,
        failed_at=row.failed_at,
        transaction_date=row.transaction_date,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _copy_txn(txn: PaymentTransaction, row: PaymentTransactionModel) -> None:
    row.id = txn.id
    row.transaction_number = txn.transaction_number
    row.order_id = txn.order_id
    row.client_id = txn.client_id
    row.transaction_type = txn.transaction_type.value
    row.method = txn.method.value
    row.amount_cents = txn.amount.cents
    row.currency = txn.amount.currency
    row.recorded_by = txn.recorded_by
    row.status = txn.status.value
    row.external_reference = txn.external_reference
    row.bank_name = txn.bank_name
    row.check_number = txn.check_number
    row.notes = txn.notes
    row.failure_reason = txn.failure_reason
    row.completed_at = txn.completed_at
    row.failed_at = txn.failed_at
    row.transaction_date = txn.transaction_date
    row.created_at = txn.created_at
    row.updated_at = txn.updated_at


def _refund_to_entity(row: RefundModel) -> Refund:
    currency = row.currency
    return Refund(
        id=row.id,
        refund_number=row.refund_number,
        order_id=row.order_id,
        client_id=row.client_id,
        original_transaction_id=row.original_transaction_id,
        refund_transaction_id=row.refund_transaction_id,
        requested_amount=Money(row.requested_amount_cents, currency),
        approved_amount=Money(row.approved_amount_cents, currency) if row.approved_amount_cents else None,
        reason=RefundReason(row.reason),
        reason_detail=row.reason_detail,
        status=RefundStatus(row.status),
        method=PaymentMethod(row.method) if row.method else None,
        rejection_reason=row.rejection_reason,
        notes=row.notes,
        requested_by=row.requested_by,
        reviewed_by=row.reviewed_by,
        approved_by=row.approved_by,
        requested_at=row.requested_at,
        reviewed_at=row.reviewed_at,
        approved_at=row.approved_at,
        rejected_at=row.rejected_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _copy_refund(refund: Refund, row: RefundModel) -> None:
    row.id = refund.id
    row.refund_number = refund.refund_number
    row.order_id = refund.order_id
    row.client_id = refund.client_id
    row.original_transaction_id = refund.original_transaction_id
    row.refund_transaction_id = refund.refund_transaction_id
    row.requested_amount_cents = refund.requested_amount.cents
    row.approved_amount_cents = refund.approved_amount.cents if refund.approved_amount else None
    row.currency = refund.requested_amount.currency
    row.reason = refund.reason.value
    row.reason_detail = refund.reason_detail
    row.status = refund.status.value
    row.method = refund.method.value if refund.method else None
    row.rejection_reason = refund.rejection_reason
    row.notes = refund.notes
    row.requested_by = refund.requested_by
    row.reviewed_by = refund.reviewed_by
    row.approved_by = refund.approved_by
    row.requested_at = refund.requested_at
    row.reviewed_at = refund.reviewed_at
    row.approved_at = refund.approved_at
    row.rejected_at = refund.rejected_at
    row.completed_at = refund.completed_at
    row.created_at = refund.created_at
    row.updated_at = refund.updated_at
