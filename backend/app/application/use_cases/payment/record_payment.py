"""RecordPayment use case."""
from __future__ import annotations
from uuid import UUID
import structlog

from app.application.dto.payment_dto import RecordPaymentDTO, PaymentResponseDTO
from app.core.exceptions import EntityNotFoundError, BusinessRuleError
from app.domain.entities.payment import PaymentTransaction, TransactionType, PaymentMethod, TransactionStatus
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_payment_repository import IPaymentRepository
from app.domain.services.order_domain_service import OrderDomainService
from app.domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


class RecordPaymentUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        payment_repo: IPaymentRepository,
    ) -> None:
        self._order_repo = order_repo
        self._payment_repo = payment_repo

    async def execute(self, dto: RecordPaymentDTO, recorded_by: UUID) -> PaymentResponseDTO:
        order = await self._order_repo.get_by_id(dto.order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", dto.order_id)

        amount = Money(dto.amount_cents, order.currency)
        OrderDomainService.validate_payment(order, amount)

        txn_number = await self._payment_repo.generate_number()
        txn = PaymentTransaction(
            order_id=order.id,
            client_id=order.client_id,
            transaction_type=TransactionType.PAYMENT,
            method=PaymentMethod(dto.method),
            amount=amount,
            recorded_by=recorded_by,
            transaction_number=txn_number,
            external_reference=dto.external_reference,
            bank_name=dto.bank_name,
            check_number=dto.check_number,
            notes=dto.notes,
        )
        txn.complete()

        # Apply to order aggregate
        order.apply_payment(amount)

        # Persist both in the same unit of work (handled by repo layer)
        saved_txn = await self._payment_repo.save(txn)
        await self._order_repo.save(order)

        logger.info(
            "payment.recorded",
            txn_id=str(saved_txn.id),
            order_id=str(order.id),
            amount_cents=dto.amount_cents,
        )
        return _to_response(saved_txn)


def _to_response(txn: PaymentTransaction) -> PaymentResponseDTO:
    return PaymentResponseDTO(
        id=txn.id,
        transaction_number=txn.transaction_number,
        order_id=txn.order_id,
        client_id=txn.client_id,
        transaction_type=txn.transaction_type.value,
        status=txn.status.value,
        method=txn.method.value,
        amount_cents=txn.amount.cents,
        currency=txn.amount.currency,
        external_reference=txn.external_reference,
        notes=txn.notes,
        completed_at=txn.completed_at,
        transaction_date=txn.transaction_date,
        created_at=txn.created_at,
    )
