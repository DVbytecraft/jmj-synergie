"""Order DTOs."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class OrderItemInputDTO(BaseModel):
    description: str = Field(..., min_length=1, max_length=1000)
    quantity: Decimal = Field(..., gt=0, decimal_places=4)
    unit_price_cents: int = Field(..., ge=0)
    unit: Optional[str] = Field(None, max_length=20)
    item_code: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    sort_order: int = Field(0, ge=0)


class OrderDeliveryItemDTO(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(..., gt=0, decimal_places=4)


class CreateOrderDTO(BaseModel):
    client_id: UUID
    currency: str = Field("XAF", min_length=3, max_length=3)
    tax_rate: Decimal = Field(Decimal("0.00"), ge=0, le=100)
    discount_cents: int = Field(0, ge=0)
    shipping_cents: int = Field(0, ge=0)
    purchase_order_ref: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None
    items: list[OrderItemInputDTO] = Field(default_factory=list)


class UpdateOrderDTO(BaseModel):
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    discount_cents: Optional[int] = Field(None, ge=0)
    shipping_cents: Optional[int] = Field(None, ge=0)
    purchase_order_ref: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[date] = None
    delivery_date: Optional[date] = None


class OrderItemResponseDTO(BaseModel):
    id: UUID
    description: str
    quantity: Decimal
    delivered_quantity: Decimal
    invoiced_quantity: Decimal
    remaining_quantity: Decimal
    invoiceable_quantity: Decimal
    unit_price_cents: int
    line_total_cents: int
    delivered_line_total_cents: int
    unit: Optional[str]
    item_code: Optional[str]
    notes: Optional[str]
    sort_order: int


class OrderResponseDTO(BaseModel):
    id: UUID
    order_number: str
    client_id: UUID
    status: str
    payment_status: str
    currency: str
    subtotal_cents: int
    tax_rate: Decimal
    tax_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int
    delivered_subtotal_cents: int
    delivered_tax_cents: int
    delivered_total_cents: int
    paid_cents: int
    refunded_cents: int
    balance_due_cents: int
    has_reliquat: bool
    fully_delivered: bool
    days_overdue: int
    purchase_order_ref: Optional[str]
    notes: Optional[str]
    due_date: Optional[date]
    delivery_date: Optional[date]
    delivered_at: Optional[datetime]
    items: list[OrderItemResponseDTO]
    created_at: datetime
    updated_at: datetime


class OrderListResponseDTO(BaseModel):
    items: list[OrderResponseDTO]
    total: int
    skip: int
    limit: int
