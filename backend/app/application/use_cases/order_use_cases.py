"""
Order Use Cases — Application layer.
Orchestrates domain entities, repositories, and services.
"""
from decimal import Decimal
from uuid import UUID

import structlog

from app.application.dto.order_dto import (
    CreateOrderDTO,
    AddOrderItemDTO,
    PaymentDTO,
    RefundDTO,
    OrderResponseDTO,
)
from app.application.mappers.order_mapper import OrderMapper
from app.core.exceptions import EntityNotFoundError, InvalidOrderStateError, InsufficientPaymentError
from app.domain.entities.order import Order, OrderItem, OrderStatus
from app.domain.repositories.order_repository import IOrderRepository

logger = structlog.get_logger()


class OrderUseCases:
    def __init__(self, order_repo: IOrderRepository):
        self._repo = order_repo

    async def create_order(self, dto: CreateOrderDTO, created_by: UUID) -> OrderResponseDTO:
        order = Order(
            client_id=dto.client_id,
            created_by=created_by,
            currency=dto.currency,
            tax_rate=dto.tax_rate,
            notes=dto.notes,
        )
        order.order_number = await self._repo.generate_order_number()

        for item_dto in dto.items:
            order.add_item(OrderItem(
                description=item_dto.description,
                quantity=item_dto.quantity,
                unit_price_cents=item_dto.unit_price_cents,
                unit=item_dto.unit,
                sort_order=item_dto.sort_order,
            ))

        saved = await self._repo.save(order)
        logger.info("order.created", order_id=str(saved.id), number=saved.order_number)
        return OrderMapper.to_response(saved)

    async def confirm_order(self, order_id: UUID) -> OrderResponseDTO:
        order = await self._get_or_raise(order_id)
        try:
            order.confirm()
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, "draft") from e
        saved = await self._repo.save(order)
        logger.info("order.confirmed", order_id=str(order_id))
        return OrderMapper.to_response(saved)

    async def record_payment(self, order_id: UUID, dto: PaymentDTO, recorded_by: UUID) -> OrderResponseDTO:
        order = await self._get_or_raise(order_id)
        if order.status == OrderStatus.CANCELLED:
            raise InvalidOrderStateError("cancelled", "active")
        if dto.amount_cents <= 0:
            raise InsufficientPaymentError(order.balance_due_cents, dto.amount_cents)
        order.apply_payment(dto.amount_cents)
        saved = await self._repo.save(order)
        logger.info("order.payment_recorded", order_id=str(order_id), amount=dto.amount_cents)
        return OrderMapper.to_response(saved)

    async def record_refund(self, order_id: UUID, dto: RefundDTO, recorded_by: UUID) -> OrderResponseDTO:
        order = await self._get_or_raise(order_id)
        try:
            order.apply_refund(dto.amount_cents)
        except ValueError as e:
            raise InsufficientPaymentError(0, dto.amount_cents) from e
        saved = await self._repo.save(order)
        logger.info("order.refund_recorded", order_id=str(order_id), amount=dto.amount_cents)
        return OrderMapper.to_response(saved)

    async def cancel_order(self, order_id: UUID) -> OrderResponseDTO:
        order = await self._get_or_raise(order_id)
        try:
            order.cancel()
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, "cancellable") from e
        saved = await self._repo.save(order)
        logger.info("order.cancelled", order_id=str(order_id))
        return OrderMapper.to_response(saved)

    async def get_order(self, order_id: UUID) -> OrderResponseDTO:
        order = await self._get_or_raise(order_id)
        return OrderMapper.to_response(order)

    async def list_orders(self, skip: int, limit: int, filters: dict) -> tuple[list[OrderResponseDTO], int]:
        orders, total = await self._repo.list_all(skip, limit, filters)
        return [OrderMapper.to_response(o) for o in orders], total

    # ─── Helpers ──────────────────────────────────────────────────────────────

    async def _get_or_raise(self, order_id: UUID) -> Order:
        order = await self._repo.get_by_id(order_id)
        if not order:
            raise EntityNotFoundError("Order", order_id)
        return order
