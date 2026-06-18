"""Product use cases — CRUD + lifecycle."""
from __future__ import annotations
from uuid import UUID

import structlog

from app.application.dto.product_dto import (
    CreateProductDTO, UpdateProductDTO,
    ProductResponseDTO, ProductListResponseDTO,
)
from app.core.exceptions import EntityNotFoundError, DuplicateEntityError, BusinessRuleError
from app.domain.entities.product import Product
from app.domain.repositories.i_product_repository import IProductRepository

logger = structlog.get_logger(__name__)


def _to_response(p: Product) -> ProductResponseDTO:
    return ProductResponseDTO(
        id=p.id,
        code=p.code,
        name=p.name,
        description=p.description,
        short_description=p.short_description,
        category=p.category,
        sub_category=p.sub_category,
        unit=p.unit,
        currency=p.currency,
        unit_price_cents=p.unit_price_cents,
        tax_rate=p.tax_rate,
        min_order_quantity=p.min_order_quantity,
        track_stock=p.track_stock,
        stock_quantity=p.stock_quantity,
        low_stock_threshold=p.low_stock_threshold,
        image_path=p.image_path,
        status=p.status.value,
        notes=p.notes,
        supplier_ref=p.supplier_ref,
        barcode=p.barcode,
        is_low_stock=p.is_low_stock,
        unit_price_tax_included_cents=p.unit_price_tax_included_cents,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ── Create ─────────────────────────────────────────────────────────────────────

class CreateProductUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(self, dto: CreateProductDTO, created_by: UUID) -> ProductResponseDTO:
        if dto.barcode:
            existing = await self._repo.list(0, 1, search=None, category=None, status=None)
            # barcode uniqueness checked at DB level — trust the constraint

        code = await self._repo.generate_code()
        try:
            product = Product(
                name=dto.name,
                unit_price_cents=dto.unit_price_cents,
                created_by=created_by,
                description=dto.description,
                short_description=dto.short_description,
                category=dto.category,
                sub_category=dto.sub_category,
                unit=dto.unit,
                currency=dto.currency,
                tax_rate=dto.tax_rate,
                min_order_quantity=dto.min_order_quantity,
                track_stock=dto.track_stock,
                stock_quantity=dto.stock_quantity,
                low_stock_threshold=dto.low_stock_threshold,
                notes=dto.notes,
                supplier_ref=dto.supplier_ref,
                barcode=dto.barcode,
                code=code,
            )
        except ValueError as e:
            raise BusinessRuleError(str(e)) from e

        saved = await self._repo.save(product)
        logger.info("product.created", product_id=str(saved.id), code=saved.code)
        return _to_response(saved)


# ── Read ───────────────────────────────────────────────────────────────────────

class GetProductUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(self, product_id: UUID) -> ProductResponseDTO:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundError("Product", product_id)
        return _to_response(product)


class ListProductsUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> ProductListResponseDTO:
        items, total = await self._repo.list(skip, limit, search, category, status)
        return ProductListResponseDTO(
            items=[_to_response(p) for p in items],
            total=total,
            skip=skip,
            limit=limit,
        )


# ── Update ─────────────────────────────────────────────────────────────────────

class UpdateProductUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(self, product_id: UUID, dto: UpdateProductDTO) -> ProductResponseDTO:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundError("Product", product_id)
        try:
            product.update(
                name=dto.name,
                description=dto.description,
                short_description=dto.short_description,
                category=dto.category,
                unit=dto.unit,
                unit_price_cents=dto.unit_price_cents,
                tax_rate=dto.tax_rate,
                min_order_quantity=dto.min_order_quantity,
                notes=dto.notes,
                supplier_ref=dto.supplier_ref,
            )
        except ValueError as e:
            raise BusinessRuleError(str(e)) from e
        saved = await self._repo.save(product)
        logger.info("product.updated", product_id=str(product_id))
        return _to_response(saved)


# ── Lifecycle ──────────────────────────────────────────────────────────────────

class ActivateProductUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(self, product_id: UUID) -> ProductResponseDTO:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundError("Product", product_id)
        try:
            product.activate()
        except ValueError as e:
            raise BusinessRuleError(str(e)) from e
        saved = await self._repo.save(product)
        logger.info("product.activated", product_id=str(product_id))
        return _to_response(saved)


class DeactivateProductUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(self, product_id: UUID) -> ProductResponseDTO:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundError("Product", product_id)
        try:
            product.deactivate()
        except ValueError as e:
            raise BusinessRuleError(str(e)) from e
        saved = await self._repo.save(product)
        logger.info("product.deactivated", product_id=str(product_id))
        return _to_response(saved)


class DeleteProductUseCase:
    def __init__(self, repo: IProductRepository) -> None:
        self._repo = repo

    async def execute(self, product_id: UUID, deleted_by: UUID) -> None:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise EntityNotFoundError("Product", product_id)
        product.soft_delete(deleted_by)
        await self._repo.save(product)
        logger.info("product.deleted", product_id=str(product_id))
