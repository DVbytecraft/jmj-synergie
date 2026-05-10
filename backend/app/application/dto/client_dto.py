"""Client DTOs — input/output contracts for use cases."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class CreateClientDTO(BaseModel):
    client_type: str = Field(..., pattern="^(individual|company|government|ngo)$")
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=6, max_length=30)
    company_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=60)
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    country: str = Field("CM", min_length=2, max_length=2)
    currency: str = Field("XAF", min_length=3, max_length=3)
    credit_limit_cents: int = Field(0, ge=0)
    payment_terms_days: int = Field(30, ge=0, le=365)
    default_tax_rate: float = Field(0.0, ge=0, le=100)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("country")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.upper()

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class UpdateClientDTO(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, min_length=6, max_length=30)
    company_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    credit_limit_cents: Optional[int] = Field(None, ge=0)
    payment_terms_days: Optional[int] = Field(None, ge=0, le=365)
    notes: Optional[str] = None


class ClientResponseDTO(BaseModel):
    id: UUID
    code: str
    client_type: str
    status: str
    full_name: str
    company_name: Optional[str]
    tax_id: Optional[str]
    email: Optional[str]
    phone: str
    address_line1: Optional[str]
    city: Optional[str]
    country: str
    currency: str
    credit_limit_cents: int
    payment_terms_days: int
    default_tax_rate: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientListResponseDTO(BaseModel):
    items: list[ClientResponseDTO]
    total: int
    skip: int
    limit: int
