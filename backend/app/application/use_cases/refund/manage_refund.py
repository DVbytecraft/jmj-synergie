"""Refund use cases — request, approve, reject, complete."""
from __future__ import annotations
from typing import Optional
from uuid import UUID

import structlog

from app.application.dto.payment_dto import (
    RequestRefundDTO, ApproveRefundDTO, RejectRefundDTO, RefundResponseDTO,
)
from app.core.exceptions import EntityNotFoundError, BusinessRuleError, PermissionDeniedError
from app.domain.entities.payment import (
    Refund, RefundReason, PaymentTransaction,
    TransactionType, PaymentMethod, TransactionStatus,
)
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_payment_repository import IPaymentRepository, IRefundRepository
from app.domain.services.order_domain_service import OrderDomainService
from app.domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


class RequestRefundUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        payment_repo: IPaymentRepository,
        refund_repo: IRefundRepository,
    ) -> None:
        self._order_repo = order_repo
        self._payment_repo = payment_repo
        self._refund_repo = refund_repo

    async def execute(self, dto: RequestRefundDTO, requested_by: UUID) -> RefundResponseDTO:
        order = await self._order_repo.get_by_id(dto.order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", dto.order_id)

        original_txn = await self._payment_repo.get_by_id(dto.original_transaction_id)
        if not original_txn or original_txn.order_id != order.id:
            raise EntityNotFoundError("PaymentTransaction", dto.original_transaction_id)

        amount = Money(dto.amount_cents, order.currency)
        OrderDomainService.validate_refund(order, amount)

        refund_number = await self._refund_repo.generate_number()
        refund = Refund(
            order_id=order.id,
            client_id=order.client_id,
            requested_amount=amount,
            reason=RefundReason(dto.reason),
            reason_detail=dto.reason_detail,
            requested_by=requested_by,
            original_transaction_id=original_txn.id,
            refund_number=refund_number,
            notes=dto.notes,
        )
        saved = await self._refund_repo.save(refund)
        logger.info("refund.requested", refund_id=str(saved.id), order_id=str(order.id))
        return _to_response(saved)


class ApproveRefundUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        payment_repo: IPaymentRepository,
        refund_repo: IRefundRepository,
    ) -> None:
        self._order_repo = order_repo
        self._payment_repo = payment_repo
        self._refund_repo = refund_repo

    async def execute(self, refund_id: UUID, dto: ApproveRefundDTO, approved_by: UUID) -> RefundResponseDTO:
        refund = await self._refund_repo.get_by_id(refund_id)
        if not refund:
            raise EntityNotFoundError("Refund", refund_id)

        approved_amount = Money(dto.approved_amount_cents, refund.requested_amount.currency) \
            if dto.approved_amount_cents else None

        try:
            refund.approve(approved_by, approved_amount)
        except ValueError as e:
            raise BusinessRuleError(str(e)) from e

        # Process the refund immediately (create reversal transaction + update order)
        order = await self._order_repo.get_by_id(refund.order_id)
        if not order:
            raise EntityNotFoundError("Order", refund.order_id)

        txn_number = await self._payment_repo.generate_number()
        refund_txn = PaymentTransaction(
            order_id=order.id,
            client_id=order.client_id,
            transaction_type=TransactionType.REFUND,
            method=PaymentMethod(dto.method),
            amount=refund.effective_amount,
            recorded_by=approved_by,
            transaction_number=txn_number,
        )
        refund_txn.complete()
        saved_txn = await self._payment_repo.save(refund_txn)

        order.apply_refund(refund.effective_amount)
        await self._order_repo.save(order)

        refund.complete(saved_txn.id)
        saved_refund = await self._refund_repo.save(refund)

        logger.info(
            "refund.approved",
            refund_id=str(refund_id),
            amount=refund.effective_amount.cents,
        )
        return _to_response(saved_refund)


class RejectRefundUseCase:
    def __init__(self, refund_repo: IRefundRepository) -> None:
        self._refund_repo = refund_repo

    async def execute(self, refund_id: UUID, dto: RejectRefundDTO, rejected_by: UUID) -> RefundResponseDTO:
        refund = await self._refund_repo.get_by_id(refund_id)
        if not refund:
            raise EntityNotFoundError("Refund", refund_id)
        try:
            refund.reject(rejected_by, dto.rejection_reason)
        except ValueError as e:
            raise BusinessRuleError(str(e)) from e
        saved = await self._refund_repo.save(refund)
        logger.info("refund.rejected", refund_id=str(refund_id))
        return _to_response(saved)


class ListRefundsUseCase:
    def __init__(self, refund_repo: IRefundRepository) -> None:
        self._refund_repo = refund_repo

    async def get_by_id(self, refund_id: UUID) -> RefundResponseDTO | None:
        refund = await self._refund_repo.get_by_id(refund_id)
        return _to_response(refund) if refund else None

    async def execute(
        self, skip: int = 0, limit: int = 20, status: str | None = None
    ) -> dict:
        refunds, total = await self._refund_repo.list(skip, limit, status)
        return {
            "items": [_to_response(r) for r in refunds],
            "total": total, "skip": skip, "limit": limit,
        }


def _to_response(r: Refund) -> RefundResponseDTO:
    return RefundResponseDTO(
        id=r.id,
        refund_number=r.refund_number,
        order_id=r.order_id,
        client_id=r.client_id,
        status=r.status.value,
        reason=r.reason.value,
        reason_detail=r.reason_detail,
        requested_amount_cents=r.requested_amount.cents,
        approved_amount_cents=r.approved_amount.cents if r.approved_amount else None,
        currency=r.requested_amount.currency,
        rejection_reason=r.rejection_reason,
        notes=r.notes,
        requested_at=r.requested_at,
        approved_at=r.approved_at,
        completed_at=r.completed_at,
        created_at=r.created_at,
    )
