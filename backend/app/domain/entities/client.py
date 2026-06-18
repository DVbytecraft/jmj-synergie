"""
Client domain entity — pure Python, zero framework dependency.
Business invariants enforced here, not in the API layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ClientType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"
    GOVERNMENT = "government"
    NGO = "ngo"


class ClientStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


@dataclass
class Client:
    # ── Required fields ───────────────────────────────────────────────────────
    full_name: str
    phone: str
    client_type: ClientType
    created_by: UUID
    organization_id: UUID

    # ── Optional fields ───────────────────────────────────────────────────────
    company_name: Optional[str] = None
    trade_name: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    country: str = "CM"
    currency: str = "XAF"
    credit_limit_cents: int = 0
    payment_terms_days: int = 30
    default_tax_rate: float = 0.0
    notes: Optional[str] = None

    # ── Identity (generated) ──────────────────────────────────────────────────
    id: UUID = field(default_factory=uuid4)
    code: str = ""
    status: ClientStatus = ClientStatus.ACTIVE
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[UUID] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Post-init validation ───────────────────────────────────────────────────

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.full_name or not self.full_name.strip():
            raise ValueError("full_name is required")
        if not self.phone or not self.phone.strip():
            raise ValueError("phone is required")
        if self.client_type == ClientType.COMPANY and not self.company_name:
            raise ValueError("company_name required for company clients")
        if self.email and not re.match(
            r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", self.email
        ):
            raise ValueError(f"Invalid email format: {self.email}")
        if self.credit_limit_cents < 0:
            raise ValueError("credit_limit_cents cannot be negative")
        if not (0 <= self.payment_terms_days <= 365):
            raise ValueError("payment_terms_days must be between 0 and 365")

    # ── Domain operations ─────────────────────────────────────────────────────

    def update(
        self,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
        address_line1: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        credit_limit_cents: Optional[int] = None,
        payment_terms_days: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        if full_name is not None:
            self.full_name = full_name
        if phone is not None:
            self.phone = phone
        if email is not None:
            self.email = email
        if company_name is not None:
            self.company_name = company_name
        if address_line1 is not None:
            self.address_line1 = address_line1
        if city is not None:
            self.city = city
        if country is not None:
            self.country = country
        if credit_limit_cents is not None:
            self.credit_limit_cents = credit_limit_cents
        if payment_terms_days is not None:
            self.payment_terms_days = payment_terms_days
        if notes is not None:
            self.notes = notes
        self._validate()
        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        if self.status == ClientStatus.BLACKLISTED:
            raise ValueError("Cannot deactivate a blacklisted client")
        self.status = ClientStatus.INACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def reactivate(self) -> None:
        self.status = ClientStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def blacklist(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Blacklist reason required")
        self.status = ClientStatus.BLACKLISTED
        self.notes = f"[BLACKLIST] {reason}\n{self.notes or ''}".strip()
        self.updated_at = datetime.now(timezone.utc)

    def soft_delete(self, deleted_by: UUID) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by
        self.updated_at = datetime.now(timezone.utc)

    @property
    def display_name(self) -> str:
        return self.company_name or self.full_name

    @property
    def is_active(self) -> bool:
        return self.status == ClientStatus.ACTIVE and not self.is_deleted
