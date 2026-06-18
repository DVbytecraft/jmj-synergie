"""SQLAlchemy implementation of IProductRepository."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.product import Product, ProductStatus
from app.domain.repositories.i_product_repository import IProductRepository
from app.infrastructure.database.models import ProductModel


class ProductRepository(IProductRepository):

    def __init__(self, session: AsyncSession, org_id: UUID | None = None) -> None:
        self._s = session
        self._org_id = org_id

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, product_id: UUID) -> Product | None:
        q = select(ProductModel).where(
            ProductModel.id == product_id,
            ProductModel.is_deleted == False,  # noqa: E712
        )
        if self._org_id is not None:
            q = q.where(ProductModel.organization_id == self._org_id)
        row = (await self._s.execute(q)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_code(self, code: str) -> Product | None:
        q = select(ProductModel).where(
            ProductModel.code == code,
            ProductModel.is_deleted == False,  # noqa: E712
        )
        if self._org_id is not None:
            q = q.where(ProductModel.organization_id == self._org_id)
        row = (await self._s.execute(q)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list(
        self,
        skip: int,
        limit: int,
        search: str | None,
        category: str | None,
        status: str | None,
    ) -> tuple[list[Product], int]:
        q = select(ProductModel).where(ProductModel.is_deleted == False)  # noqa: E712
        if self._org_id is not None:
            q = q.where(ProductModel.organization_id == self._org_id)

        if search:
            like = f"%{search}%"
            q = q.where(or_(
                ProductModel.name.ilike(like),
                ProductModel.code.ilike(like),
                ProductModel.description.ilike(like),
                ProductModel.supplier_ref.ilike(like),
            ))
        if category:
            q = q.where(ProductModel.category == category)
        if status:
            q = q.where(ProductModel.status == status)

        total = (await self._s.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()

        rows = (await self._s.execute(
            q.order_by(ProductModel.name).offset(skip).limit(limit)
        )).scalars().all()

        return [_to_entity(r) for r in rows], total

    # ── Write ─────────────────────────────────────────────────────────────────

    async def save(self, product: Product) -> Product:
        row = await self._s.get(ProductModel, product.id)
        if row is None:
            row = ProductModel()
            self._s.add(row)
        _copy_to_model(product, row)
        if self._org_id is not None and row.organization_id is None:
            row.organization_id = self._org_id
        await self._s.flush()
        await self._s.refresh(row)
        return _to_entity(row)

    async def generate_code(self) -> str:
        q = select(func.count(ProductModel.id))
        if self._org_id is not None:
            q = q.where(ProductModel.organization_id == self._org_id)
        count = (await self._s.execute(q)).scalar_one()
        return f"PROD-{count + 1:05d}"


# ── Mapper helpers ─────────────────────────────────────────────────────────────

def _to_entity(row: ProductModel) -> Product:
    return Product(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        short_description=row.short_description,
        category=row.category,
        sub_category=row.sub_category,
        unit=row.unit,
        currency=row.currency,
        unit_price_cents=row.unit_price_cents,
        tax_rate=float(row.tax_rate),
        min_order_quantity=int(row.min_order_quantity),
        track_stock=row.track_stock,
        stock_quantity=int(row.stock_quantity) if row.stock_quantity is not None else None,
        low_stock_threshold=int(row.low_stock_threshold) if row.low_stock_threshold is not None else None,
        image_path=row.image_path,
        status=ProductStatus(row.status),
        notes=row.notes,
        supplier_ref=row.supplier_ref,
        barcode=row.barcode,
        created_by=row.created_by,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _copy_to_model(product: Product, row: ProductModel) -> None:
    row.id = product.id
    row.code = product.code
    row.name = product.name
    row.description = product.description
    row.short_description = product.short_description
    row.category = product.category
    row.sub_category = product.sub_category
    row.unit = product.unit
    row.currency = product.currency
    row.unit_price_cents = product.unit_price_cents
    row.tax_rate = Decimal(str(product.tax_rate))
    row.min_order_quantity = int(product.min_order_quantity)
    row.track_stock = product.track_stock
    row.stock_quantity = int(product.stock_quantity) if product.stock_quantity is not None else None
    row.low_stock_threshold = int(product.low_stock_threshold) if product.low_stock_threshold is not None else None
    row.image_path = product.image_path
    row.status = product.status.value
    row.notes = product.notes
    row.supplier_ref = product.supplier_ref
    row.barcode = product.barcode
    row.created_by = product.created_by
    row.is_deleted = product.is_deleted
    row.deleted_at = product.deleted_at
    row.created_at = product.created_at
    row.updated_at = product.updated_at
