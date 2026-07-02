"""
Stock endpoints.
  GET  /stock/                         → liste tous les produits avec leur stock
  GET  /stock/{product_id}             → stock d'un produit
  POST /stock/{product_id}/adjust      → ajuster le stock manuellement
  PUT  /stock/{product_id}/config      → configurer track_stock + low_stock_threshold
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, ManagerUser, DB, _require_org
from app.infrastructure.database.models import ProductModel
from app.infrastructure.database.session import get_db_session

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class StockItemDTO(BaseModel):
    id: UUID
    code: str
    name: str
    category: Optional[str]
    unit: Optional[str]
    unit_price_cents: int
    currency: str
    track_stock: bool
    stock_quantity: Optional[int]
    low_stock_threshold: Optional[int]
    is_low_stock: bool
    status: str

    model_config = {"from_attributes": True}


class StockListDTO(BaseModel):
    items: list[StockItemDTO]
    total: int
    alerts_count: int


class StockAdjustDTO(BaseModel):
    delta: int = Field(..., description="Positif = entrée stock, négatif = sortie")
    reason: Literal["restock", "loss", "correction", "sale", "return"] = "correction"
    note: Optional[str] = Field(None, max_length=500)


class StockConfigDTO(BaseModel):
    track_stock: bool
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_low_stock(row: ProductModel) -> bool:
    if not row.track_stock or row.low_stock_threshold is None:
        return False
    qty = row.stock_quantity or 0
    return qty <= row.low_stock_threshold


def _to_dto(row: ProductModel) -> StockItemDTO:
    return StockItemDTO(
        id=row.id,
        code=row.code,
        name=row.name,
        category=row.category,
        unit=row.unit,
        unit_price_cents=row.unit_price_cents,
        currency=row.currency,
        track_stock=row.track_stock,
        stock_quantity=row.stock_quantity,
        low_stock_threshold=row.low_stock_threshold,
        is_low_stock=_is_low_stock(row),
        status=row.status,
    )


async def _get_product_or_404(
    product_id: UUID,
    org_id: UUID,
    db: AsyncSession,
) -> ProductModel:
    q = select(ProductModel).where(
        ProductModel.id == product_id,
        ProductModel.organization_id == org_id,
        ProductModel.is_deleted == False,  # noqa: E712
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")
    return row


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=StockListDTO,
    summary="Liste des stocks produits",
)
async def list_stock(
    current_user: CurrentUser,
    db: DB,
    alerts_only: bool = Query(False, description="Filtrer uniquement les produits en stock bas"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> StockListDTO:
    org_id = _require_org(current_user)

    base_filters = [
        ProductModel.organization_id == org_id,
        ProductModel.is_deleted == False,  # noqa: E712
        ProductModel.track_stock == True,  # noqa: E712
    ]
    low_stock_expr = and_(
        ProductModel.low_stock_threshold.isnot(None),
        func.coalesce(ProductModel.stock_quantity, 0) <= ProductModel.low_stock_threshold,
    )

    list_filters = list(base_filters)
    if alerts_only:
        list_filters.append(low_stock_expr)

    total = (
        await db.execute(select(func.count()).select_from(ProductModel).where(*list_filters))
    ).scalar_one()

    if alerts_only:
        alerts_count = total
    else:
        alerts_count = (
            await db.execute(
                select(func.count()).select_from(ProductModel).where(*base_filters, low_stock_expr)
            )
        ).scalar_one()

    rows = (
        await db.execute(
            select(ProductModel)
            .where(*list_filters)
            .order_by(ProductModel.name)
            .offset(skip)
            .limit(limit)
        )
    ).scalars().all()
    items = [_to_dto(r) for r in rows]

    return StockListDTO(items=items, total=total, alerts_count=alerts_count)


@router.get(
    "/{product_id}",
    response_model=StockItemDTO,
    summary="Stock d'un produit",
)
async def get_stock(
    product_id: UUID,
    current_user: CurrentUser,
    db: DB,
) -> StockItemDTO:
    org_id = _require_org(current_user)
    row = await _get_product_or_404(product_id, org_id, db)
    return _to_dto(row)


@router.post(
    "/{product_id}/adjust",
    response_model=StockItemDTO,
    summary="Ajuster le stock manuellement",
)
async def adjust_stock(
    product_id: UUID,
    body: StockAdjustDTO,
    current_user: ManagerUser,
    db: DB,
) -> StockItemDTO:
    org_id = _require_org(current_user)
    row = await _get_product_or_404(product_id, org_id, db)

    if not row.track_stock:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ce produit ne suit pas l'inventaire (track_stock=false)",
        )

    current_qty = row.stock_quantity or 0
    new_qty = current_qty + body.delta

    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Stock insuffisant : disponible={current_qty}, ajustement={body.delta}",
        )

    row.stock_quantity = new_qty
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(row)
    return _to_dto(row)


@router.put(
    "/{product_id}/config",
    response_model=StockItemDTO,
    summary="Configurer le suivi de stock",
)
async def config_stock(
    product_id: UUID,
    body: StockConfigDTO,
    current_user: ManagerUser,
    db: DB,
) -> StockItemDTO:
    org_id = _require_org(current_user)
    row = await _get_product_or_404(product_id, org_id, db)

    row.track_stock = body.track_stock
    if body.low_stock_threshold is not None:
        row.low_stock_threshold = body.low_stock_threshold
    if body.stock_quantity is not None:
        row.stock_quantity = body.stock_quantity
    row.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(row)
    return _to_dto(row)
