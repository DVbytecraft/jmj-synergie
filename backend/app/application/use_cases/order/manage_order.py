"""
Order lifecycle use cases — confirm, cancel, update, delete, get, list.
Grouped to reduce file count without compromising SRP.
"""
from __future__ import annotations
from uuid import UUID

import structlog

from app.application.dto.order_dto import (
    UpdateOrderDTO,
    OrderResponseDTO,
    OrderListResponseDTO,
    OrderItemInputDTO,
    OrderDeliveryItemDTO,
)
from app.application.mappers.order_mapper import OrderMapper
from app.core.exceptions import EntityNotFoundError, InvalidOrderStateError, PermissionDeniedError
from app.domain.entities.order import OrderItem, OrderStatus
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.value_objects.money import Money

logger = structlog.get_logger(__name__)


class GetOrderUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        return OrderMapper.to_response_dto(order)


class ListOrdersUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        skip: int = 0,
        limit: int = 20,
        client_id: UUID | None = None,
        status: str | None = None,
        payment_status: str | None = None,
        search: str | None = None,
    ) -> OrderListResponseDTO:
        orders, total = await self._repo.list(skip, limit, client_id, status, payment_status, search)
        return OrderListResponseDTO(
            items=[OrderMapper.to_response_dto(o) for o in orders],
            total=total, skip=skip, limit=limit,
        )


class UpdateOrderUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, dto: UpdateOrderDTO) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        if order.status != OrderStatus.DRAFT:
            raise InvalidOrderStateError(order.status.value, "draft")

        if dto.tax_rate is not None:
            order.tax_rate = dto.tax_rate
        if dto.discount_cents is not None:
            order.discount_cents = dto.discount_cents
        if dto.shipping_cents is not None:
            order.shipping_cents = dto.shipping_cents
        if dto.purchase_order_ref is not None:
            order.purchase_order_ref = dto.purchase_order_ref
        if dto.notes is not None:
            order.notes = dto.notes
        if dto.due_date is not None:
            order.due_date = dto.due_date
        if dto.delivery_date is not None:
            order.delivery_date = dto.delivery_date

        saved = await self._repo.save(order)
        logger.info("order.updated", order_id=str(order_id))
        return OrderMapper.to_response_dto(saved)


class ConfirmOrderUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, confirmed_by: UUID) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        try:
            order.confirm(confirmed_by)
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, "draft") from e
        saved = await self._repo.save(order)
        logger.info("order.confirmed", order_id=str(order_id))
        return OrderMapper.to_response_dto(saved)


class CancelOrderUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, cancelled_by: UUID, reason: str | None = None) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        try:
            order.cancel(cancelled_by, reason)
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, "cancellable") from e
        saved = await self._repo.save(order)
        logger.info("order.cancelled", order_id=str(order_id))
        return OrderMapper.to_response_dto(saved)


class DeleteOrderUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, deleted_by: UUID) -> None:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        if order.status not in (OrderStatus.DRAFT, OrderStatus.CANCELLED):
            raise InvalidOrderStateError(order.status.value, ["draft", "cancelled"])
        order.soft_delete(deleted_by)
        await self._repo.save(order)
        logger.info("order.deleted", order_id=str(order_id))


class AddOrderItemUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, dto: OrderItemInputDTO) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        item = OrderItem(
            description=dto.description,
            quantity=dto.quantity,
            unit_price=Money(dto.unit_price_cents, order.currency),
            unit=dto.unit,
            item_code=dto.item_code,
            notes=dto.notes,
            sort_order=dto.sort_order,
        )
        try:
            order.add_item(item)
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, ["draft", "confirmed"]) from e
        saved = await self._repo.save(order)
        return OrderMapper.to_response_dto(saved)


class RemoveOrderItemUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, item_id: UUID) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        try:
            order.remove_item(item_id)
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, "draft") from e
        saved = await self._repo.save(order)
        return OrderMapper.to_response_dto(saved)


class RecordDeliveryUseCase:
    def __init__(self, repo: IOrderRepository) -> None:
        self._repo = repo

    async def execute(self, order_id: UUID, deliveries: list[OrderDeliveryItemDTO], actor: UUID) -> OrderResponseDTO:
        order = await self._repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)
        try:
            order.record_delivery(actor, [(item.item_id, item.quantity) for item in deliveries])
        except ValueError as e:
            raise InvalidOrderStateError(order.status.value, "deliverable") from e
        saved = await self._repo.save(order)
        logger.info("order.delivery_recorded", order_id=str(order_id))
        return OrderMapper.to_response_dto(saved)
