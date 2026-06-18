"""Payment & Refund DTOs."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RecordPaymentDTO(BaseModel):
    order_id: UUID
    amount_cents: int = Field(..., gt=0, description="Amount in smallest currency unit")
    method: str = Field(..., pattern="^(cash|bank_transfer|mobile_money|check|card)$")
    external_reference: Optional[str] = Field(None, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=100)
    check_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class PaymentResponseDTO(BaseModel):
    id: UUID
    transaction_number: str
    order_id: Optional[UUID]
    client_id: UUID
    transaction_type: str
    status: str
    method: str
    amount_cents: int
    currency: str
    external_reference: Optional[str]
    notes: Optional[str]
    completed_at: Optional[datetime]
    transaction_date: datetime
    created_at: datetime


class RequestRefundDTO(BaseModel):
    order_id: UUID
    original_transaction_id: UUID
    amount_cents: int = Field(..., gt=0)
    reason: str = Field(..., pattern="^(product_defect|wrong_item|not_delivered|customer_request|duplicate_payment|billing_error|other)$")
    reason_detail: str = Field(..., min_length=10, max_length=500)
    notes: Optional[str] = None


class ApproveRefundDTO(BaseModel):
    approved_amount_cents: Optional[int] = Field(None, gt=0)
    method: str = Field(..., pattern="^(cash|bank_transfer|mobile_money|check|card)$")


class RejectRefundDTO(BaseModel):
    rejection_reason: str = Field(..., min_length=5, max_length=500)


class RefundResponseDTO(BaseModel):
    id: UUID
    refund_number: str
    order_id: UUID
    client_id: UUID
    status: str
    reason: str
    reason_detail: str
    requested_amount_cents: int
    approved_amount_cents: Optional[int]
    currency: str
    rejection_reason: Optional[str]
    notes: Optional[str]
    requested_at: datetime
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
