"""Product DTOs — input/output contracts."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateProductDTO(BaseModel):
    name: str               = Field(..., min_length=1, max_length=255)
    unit_price_cents: int   = Field(..., ge=0, description="Prix unitaire en centimes XAF")
    description: Optional[str]       = Field(None, max_length=5000)
    short_description: Optional[str] = Field(None, max_length=500)
    category: Optional[str]          = Field(None, max_length=100)
    sub_category: Optional[str]      = Field(None, max_length=100)
    unit: Optional[str]              = Field(None, max_length=20, description="kg, m², pièce...")
    currency: str           = Field("XAF", min_length=3, max_length=3)
    tax_rate: float         = Field(0.0, ge=0, le=100)
    min_order_quantity: float = Field(1.0, gt=0)
    track_stock: bool       = False
    stock_quantity: Optional[float]        = Field(None, ge=0)
    low_stock_threshold: Optional[float]   = Field(None, ge=0)
    notes: Optional[str]    = Field(None, max_length=2000)
    supplier_ref: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str]  = Field(None, max_length=60)

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class UpdateProductDTO(BaseModel):
    name: Optional[str]             = Field(None, min_length=1, max_length=255)
    unit_price_cents: Optional[int] = Field(None, ge=0)
    description: Optional[str]      = Field(None, max_length=5000)
    short_description: Optional[str]= Field(None, max_length=500)
    category: Optional[str]         = Field(None, max_length=100)
    sub_category: Optional[str]     = Field(None, max_length=100)
    unit: Optional[str]             = Field(None, max_length=20)
    tax_rate: Optional[float]       = Field(None, ge=0, le=100)
    min_order_quantity: Optional[float] = Field(None, gt=0)
    notes: Optional[str]            = None
    supplier_ref: Optional[str]     = Field(None, max_length=100)


class ProductResponseDTO(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str]
    short_description: Optional[str]
    category: Optional[str]
    sub_category: Optional[str]
    unit: Optional[str]
    currency: str
    unit_price_cents: int
    tax_rate: float
    min_order_quantity: float
    track_stock: bool
    stock_quantity: Optional[float]
    low_stock_threshold: Optional[float]
    image_path: Optional[str]
    status: str
    notes: Optional[str]
    supplier_ref: Optional[str]
    barcode: Optional[str]
    is_low_stock: bool
    unit_price_tax_included_cents: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponseDTO(BaseModel):
    items: list[ProductResponseDTO]
    total: int
    skip: int
    limit: int
