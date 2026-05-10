"""
SQLAlchemy implementation of IOrderRepository.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.order import Order as OrderEntity, OrderItem as ItemEntity
from app.domain.entities.order import OrderStatus, PaymentStatus
from app.domain.repositories.order_repository import IOrderRepository
from app.infrastructure.database import models as m


class OrderRepositoryImpl(IOrderRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, order_id: UUID) -> OrderEntity | None:
        result = await self._db.execute(
            select(m.Order)
            .options(selectinload(m.Order.items))
            .where(m.Order.id == order_id, m.Order.is_deleted == False)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_number(self, number: str) -> OrderEntity | None:
        result = await self._db.execute(
            select(m.Order).options(selectinload(m.Order.items))
            .where(m.Order.order_number == number, m.Order.is_deleted == False)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_client(self, client_id: UUID, skip: int, limit: int) -> list[OrderEntity]:
        result = await self._db.execute(
            select(m.Order)
            .options(selectinload(m.Order.items))
            .where(m.Order.client_id == client_id, m.Order.is_deleted == False)
            .order_by(m.Order.created_at.desc())
            .offset(skip).limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_all(self, skip: int, limit: int, filters: dict) -> tuple[list[OrderEntity], int]:
        q = select(m.Order).options(selectinload(m.Order.items)).where(m.Order.is_deleted == False)
        if "status" in filters:
            q = q.where(m.Order.status == filters["status"])
        if "client_id" in filters:
            q = q.where(m.Order.client_id == filters["client_id"])

        count_result = await self._db.execute(select(func.count()).select_from(q.subquery()))
        total = count_result.scalar_one()

        result = await self._db.execute(q.order_by(m.Order.created_at.desc()).offset(skip).limit(limit))
        entities = [self._to_entity(r) for r in result.scalars().all()]
        return entities, total

    async def save(self, entity: OrderEntity) -> OrderEntity:
        result = await self._db.execute(
            select(m.Order).where(m.Order.id == entity.id)
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = m.Order(id=entity.id)
            self._db.add(row)

        # Sync fields
        row.order_number = entity.order_number
        row.client_id = entity.client_id
        row.created_by = entity.created_by
        row.status = m.OrderStatus(entity.status.value)
        row.payment_status = m.PaymentStatus(entity.payment_status.value)
        row.currency = entity.currency
        row.tax_rate = entity.tax_rate
        row.subtotal_cents = entity.subtotal_cents
        row.tax_cents = entity.tax_cents
        row.discount_cents = entity.discount_cents
        row.total_cents = entity.total_cents
        row.paid_cents = entity.paid_cents
        row.refunded_cents = entity.refunded_cents
        row.notes = entity.notes

        # Replace items
        await self._db.execute(
            m.OrderItem.__table__.delete().where(m.OrderItem.order_id == entity.id)
        )
        for item in entity.items:
            self._db.add(m.OrderItem(
                id=item.id,
                order_id=entity.id,
                description=item.description,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_cents=item.total_cents,
                unit=item.unit,
                sort_order=item.sort_order,
            ))

        await self._db.flush()
        return entity

    async def delete(self, order_id: UUID) -> None:
        result = await self._db.execute(select(m.Order).where(m.Order.id == order_id))
        row = result.scalar_one_or_none()
        if row:
            row.is_deleted = True
            row.deleted_at = datetime.now(timezone.utc)

    async def generate_order_number(self) -> str:
        now = datetime.now(timezone.utc)
        prefix = f"CMD-{now.strftime('%Y%m')}"
        result = await self._db.execute(
            select(func.count(m.Order.id)).where(m.Order.order_number.like(f"{prefix}%"))
        )
        count = result.scalar_one()
        return f"{prefix}-{count + 1:04d}"

    @staticmethod
    def _to_entity(row: m.Order) -> OrderEntity:
        entity = OrderEntity(
            id=row.id,
            order_number=row.order_number,
            client_id=row.client_id,
            created_by=row.created_by,
            currency=row.currency,
            tax_rate=row.tax_rate,
            discount_cents=row.discount_cents,
            notes=row.notes,
            paid_cents=row.paid_cents,
            refunded_cents=row.refunded_cents,
            status=OrderStatus(row.status.value),
            payment_status=PaymentStatus(row.payment_status.value),
            created_at=row.created_at,
        )
        entity.items = [
            ItemEntity(
                id=item.id,
                description=item.description,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                unit=item.unit,
                sort_order=item.sort_order,
            )
            for item in (row.items or [])
        ]
        return entity
