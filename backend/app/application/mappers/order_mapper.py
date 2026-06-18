"""Order mapper — domain entity ↔ DTO."""
from decimal import Decimal

from app.domain.entities.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.domain.value_objects.money import Money
from app.application.dto.order_dto import (
    CreateOrderDTO,
    OrderResponseDTO,
    OrderItemResponseDTO,
)


class OrderMapper:

    @staticmethod
    def from_create_dto(dto: CreateOrderDTO, created_by, organization_id, order_number: str) -> Order:
        order = Order(
            client_id=dto.client_id,
            created_by=created_by,
            organization_id=organization_id,
            currency=dto.currency,
            tax_rate=dto.tax_rate,
            discount_cents=dto.discount_cents,
            shipping_cents=dto.shipping_cents,
            purchase_order_ref=dto.purchase_order_ref,
            notes=dto.notes,
            due_date=dto.due_date,
            delivery_date=dto.delivery_date,
            order_number=order_number,
        )
        for i, item_dto in enumerate(dto.items):
            order.add_item(OrderItem(
                description=item_dto.description,
                quantity=item_dto.quantity,
                unit_price=Money(item_dto.unit_price_cents, dto.currency),
                unit=item_dto.unit,
                item_code=item_dto.item_code,
                notes=item_dto.notes,
                sort_order=item_dto.sort_order if item_dto.sort_order else i,
            ))
        return order

    @staticmethod
    def to_response_dto(order: Order) -> OrderResponseDTO:
        return OrderResponseDTO(
            id=order.id,
            order_number=order.order_number,
            client_id=order.client_id,
            status=order.status.value,
            payment_status=order.payment_status.value,
            currency=order.currency,
            subtotal_cents=order.subtotal.cents,
            tax_rate=order.tax_rate,
            tax_cents=order.tax_amount.cents,
            discount_cents=order.discount_cents,
            shipping_cents=order.shipping_cents,
            total_cents=order.total.cents,
            delivered_subtotal_cents=order.delivered_subtotal.cents,
            delivered_tax_cents=order.delivered_tax_amount.cents,
            delivered_total_cents=order.delivered_total.cents,
            paid_cents=order.paid_cents,
            refunded_cents=order.refunded_cents,
            balance_due_cents=order.balance_due.cents,
            has_reliquat=order.has_reliquat,
            fully_delivered=order.fully_delivered,
            days_overdue=order.days_overdue,
            purchase_order_ref=order.purchase_order_ref,
            notes=order.notes,
            due_date=order.due_date,
            delivery_date=order.delivery_date,
            delivered_at=order.delivered_at,
            items=[
                OrderItemResponseDTO(
                    id=item.id,
                    description=item.description,
                    quantity=item.quantity,
                    delivered_quantity=item.delivered_quantity,
                    invoiced_quantity=item.invoiced_quantity,
                    remaining_quantity=item.remaining_quantity,
                    invoiceable_quantity=item.invoiceable_quantity,
                    unit_price_cents=item.unit_price.cents,
                    line_total_cents=item.line_total.cents,
                    delivered_line_total_cents=item.delivered_line_total.cents,
                    unit=item.unit,
                    item_code=item.item_code,
                    notes=item.notes,
                    sort_order=item.sort_order,
                )
                for item in order.items
            ],
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
