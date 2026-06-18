"""SQLAlchemy implementation of IOrderRepository."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.value_objects.money import Money
from app.infrastructure.database.models import OrderModel, OrderItemModel


class OrderRepository(IOrderRepository):

    def __init__(self, session: AsyncSession, organization_id: UUID | None = None) -> None:
        self._s = session
        self._org_id = organization_id

    async def get_by_id(self, order_id: UUID) -> Order | None:
        row = (await self._s.execute(
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(
                OrderModel.id == order_id,
                OrderModel.is_deleted == False,  # noqa: E712
                *( [OrderModel.organization_id == self._org_id] if self._org_id else [] ),
            )
        )).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_number(self, number: str) -> Order | None:
        row = (await self._s.execute(
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(
                OrderModel.order_number == number,
                OrderModel.is_deleted == False,
                *( [OrderModel.organization_id == self._org_id] if self._org_id else [] ),
            )  # noqa
        )).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list(
        self,
        skip: int,
        limit: int,
        client_id: UUID | None,
        status: str | None,
        payment_status: str | None,
    ) -> tuple[list[Order], int]:
        q = select(OrderModel).where(OrderModel.is_deleted == False)  # noqa
        if self._org_id:
            q = q.where(OrderModel.organization_id == self._org_id)
        if client_id:
            q = q.where(OrderModel.client_id == client_id)
        if status:
            q = q.where(OrderModel.status == status)
        if payment_status:
            q = q.where(OrderModel.payment_status == payment_status)

        total = (await self._s.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()

        rows = (await self._s.execute(
            q.options(selectinload(OrderModel.items))
            .order_by(OrderModel.created_at.desc())
            .offset(skip).limit(limit)
        )).scalars().all()

        return [_to_entity(r) for r in rows], total

    async def save(self, order: Order) -> Order:
        row = (await self._s.execute(
            select(OrderModel).options(selectinload(OrderModel.items))
            .where(OrderModel.id == order.id)
        )).scalar_one_or_none()

        if row is None:
            row = OrderModel()
            self._s.add(row)

        _copy_to_model(order, row)

        # Sync items — delete all and re-insert (simple, correct for small lists)
        for item_row in list(row.items):
            await self._s.delete(item_row)
        await self._s.flush()

        for item in order.items:
            self._s.add(OrderItemModel(
                id=item.id,
                order_id=order.id,
                sort_order=item.sort_order,
                item_code=item.item_code,
                description=item.description,
                unit=item.unit,
                notes=item.notes,
                quantity=item.quantity,
                delivered_quantity=item.delivered_quantity,
                invoiced_quantity=item.invoiced_quantity,
                unit_price_cents=item.unit_price.cents,
            ))

        await self._s.flush()
        await self._s.refresh(row)
        # Re-fetch items after insert
        await self._s.refresh(row, ["items"])
        return _to_entity(row)

    async def delete(self, order_id: UUID) -> None:
        row = await self._s.get(OrderModel, order_id)
        if row:
            row.is_deleted = True
            row.deleted_at = datetime.now(timezone.utc)

    async def generate_number(self) -> str:
        from datetime import datetime
        import sqlalchemy as sa
        now = datetime.now(timezone.utc)
        prefix = f"CMD-{now.strftime('%Y%m')}"
        result = await self._s.execute(sa.text("SELECT nextval('seq_order_number')"))
        seq = result.scalar_one()
        return f"{prefix}-{seq:04d}"


def _to_entity(row: OrderModel) -> Order:
    currency = row.currency
    order = Order(
        id=row.id,
        order_number=row.order_number,
        client_id=row.client_id,
        created_by=row.created_by,
        organization_id=row.organization_id,
        currency=currency,
        tax_rate=row.tax_rate,
        discount_cents=row.discount_cents,
        shipping_cents=row.shipping_cents,
        paid_cents=row.paid_cents,
        refunded_cents=row.refunded_cents,
        status=OrderStatus(row.status),
        payment_status=PaymentStatus(row.payment_status),
        purchase_order_ref=row.purchase_order_ref,
        notes=row.notes,
        due_date=row.due_date,
        delivery_date=row.delivery_date,
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
        delivered_at=row.delivered_at,
        cancelled_at=row.cancelled_at,
        cancelled_by=row.cancelled_by,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    order.items = [
        OrderItem(
            id=i.id,
            description=i.description,
            quantity=i.quantity,
            delivered_quantity=i.delivered_quantity,
            invoiced_quantity=i.invoiced_quantity,
            unit_price=Money(i.unit_price_cents, currency),
            unit=i.unit,
            item_code=i.item_code,
            notes=i.notes,
            sort_order=i.sort_order,
            created_at=i.created_at,
        )
        for i in (row.items or [])
    ]
    return order


def _copy_to_model(order: Order, row: OrderModel) -> None:
    row.id = order.id
    row.organization_id = order.organization_id
    row.order_number = order.order_number
    row.client_id = order.client_id
    row.created_by = order.created_by
    row.status = order.status.value
    row.payment_status = order.payment_status.value
    row.currency = order.currency
    row.tax_rate = order.tax_rate
    row.discount_cents = order.discount_cents
    row.shipping_cents = order.shipping_cents
    row.paid_cents = order.paid_cents
    row.refunded_cents = order.refunded_cents
    row.purchase_order_ref = order.purchase_order_ref
    row.notes = order.notes
    row.due_date = order.due_date
    row.delivery_date = order.delivery_date
    row.confirmed_by = order.confirmed_by
    row.confirmed_at = order.confirmed_at
    row.delivered_at = order.delivered_at
    row.cancelled_at = order.cancelled_at
    row.cancelled_by = order.cancelled_by
    row.is_deleted = order.is_deleted
    row.deleted_at = order.deleted_at
    row.deleted_by = order.deleted_by
    row.created_at = order.created_at
    row.updated_at = order.updated_at
