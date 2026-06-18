"""
Product domain entity — catalogue centralisé des produits/services.
Pure Python, zero framework dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ProductStatus(str, Enum):
    ACTIVE       = "active"
    INACTIVE     = "inactive"
    DISCONTINUED = "discontinued"
    DRAFT        = "draft"


@dataclass
class Product:
    # ── Required ──────────────────────────────────────────────────────────────
    name: str
    unit_price_cents: int
    created_by: UUID

    # ── Optional ──────────────────────────────────────────────────────────────
    description: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    unit: Optional[str] = None
    currency: str = "XAF"
    tax_rate: float = 0.0
    min_order_quantity: int = 1
    track_stock: bool = False
    stock_quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    image_path: Optional[str] = None
    notes: Optional[str] = None
    supplier_ref: Optional[str] = None
    barcode: Optional[str] = None

    # ── Generated ─────────────────────────────────────────────────────────────
    id: UUID = field(default_factory=uuid4)
    code: str = ""
    status: ProductStatus = ProductStatus.ACTIVE
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name est obligatoire")
        if self.unit_price_cents < 0:
            raise ValueError("unit_price_cents ne peut pas être négatif")
        if not (0 <= self.tax_rate <= 100):
            raise ValueError("tax_rate doit être entre 0 et 100")
        if self.min_order_quantity <= 0:
            raise ValueError("min_order_quantity doit être > 0")

    # ── Domain operations ─────────────────────────────────────────────────────

    def update(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        short_description: Optional[str] = None,
        category: Optional[str] = None,
        unit: Optional[str] = None,
        unit_price_cents: Optional[int] = None,
        tax_rate: Optional[float] = None,
        min_order_quantity: Optional[int] = None,
        notes: Optional[str] = None,
        supplier_ref: Optional[str] = None,
    ) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if short_description is not None:
            self.short_description = short_description
        if category is not None:
            self.category = category
        if unit is not None:
            self.unit = unit
        if unit_price_cents is not None:
            self.unit_price_cents = unit_price_cents
        if tax_rate is not None:
            self.tax_rate = tax_rate
        if min_order_quantity is not None:
            self.min_order_quantity = min_order_quantity
        if notes is not None:
            self.notes = notes
        if supplier_ref is not None:
            self.supplier_ref = supplier_ref
        self._validate()
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        if self.is_deleted:
            raise ValueError("Impossible d'activer un produit supprimé")
        self.status = ProductStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        if self.status == ProductStatus.DISCONTINUED:
            raise ValueError("Un produit arrêté ne peut pas être désactivé")
        self.status = ProductStatus.INACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def discontinue(self) -> None:
        self.status = ProductStatus.DISCONTINUED
        self.updated_at = datetime.now(timezone.utc)

    def soft_delete(self, deleted_by: UUID) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.status = ProductStatus.INACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def adjust_stock(self, delta: int) -> None:
        """Adjust stock quantity (positive = in, negative = out)."""
        if not self.track_stock:
            raise ValueError("Ce produit ne suit pas l'inventaire")
        current = self.stock_quantity or 0
        new_qty = current + delta
        if new_qty < 0:
            raise ValueError(f"Stock insuffisant : disponible={current}, demandé={abs(delta)}")
        self.stock_quantity = new_qty
        self.updated_at = datetime.now(timezone.utc)

    @property
    def is_low_stock(self) -> bool:
        if not self.track_stock or self.low_stock_threshold is None:
            return False
        return (self.stock_quantity or 0) <= self.low_stock_threshold

    @property
    def is_available(self) -> bool:
        return self.status == ProductStatus.ACTIVE and not self.is_deleted

    @property
    def unit_price_tax_included_cents(self) -> int:
        return round(self.unit_price_cents * (1 + self.tax_rate / 100))
