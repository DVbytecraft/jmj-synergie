"""
SQLAlchemy ORM models.
Kept strictly in the infrastructure layer — domain entities never import from here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum as SAEnum,
    ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Users ─────────────────────────────────────────────────────────────────────

class OrganizationModel(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Champs juridiques / commerciaux (Cameroun et zone OHADA)
    rccm: Mapped[str | None] = mapped_column(String(100), nullable=True)   # Registre du Commerce
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Coordonnées bancaires pour mention sur factures
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Logo affiché dans l'en-tête des documents PDF
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    email: Mapped[str]      = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str]  = mapped_column(String(255), nullable=False)
    role: Mapped[str]       = mapped_column(String(30), nullable=False, default="operator")
    status: Mapped[str]     = mapped_column(String(30), nullable=False, default="active")
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # OTP vérification email
    email_otp_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_otp_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class IssuerProfileModel(Base):
    __tablename__ = "issuer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    profile_type: Mapped[str] = mapped_column(String(20), nullable=False, default="business")
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signature_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    footer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auto_send_documents: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    primary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    font_family: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stamp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tax_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ─── Clients ───────────────────────────────────────────────────────────────────

class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    code: Mapped[str]       = mapped_column(String(20), nullable=False, index=True)
    client_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str]     = mapped_column(String(20), nullable=False, default="active")
    full_name: Mapped[str]  = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[str | None]  = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None]        = mapped_column(String(60), nullable=True)
    email: Mapped[str | None]         = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str]      = mapped_column(String(30), nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None]          = mapped_column(String(100), nullable=True)
    country: Mapped[str]    = mapped_column(String(2), nullable=False, default="CM")
    currency: Mapped[str]   = mapped_column(String(3), nullable=False, default="XAF")
    credit_limit_cents: Mapped[int]  = mapped_column(BigInteger, default=0)
    payment_terms_days: Mapped[int]  = mapped_column(SmallInteger, default=30)
    default_tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    notes: Mapped[str | None]        = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID]    = mapped_column(ForeignKey("users.id"), nullable=False)
    is_deleted: Mapped[bool]         = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    orders: Mapped[list[OrderModel]] = relationship("OrderModel", back_populates="client")


# ─── Orders ─────────────────────────────────────────────────────────────────────

class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    order_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str]     = mapped_column(String(30), nullable=False, default="draft", index=True)
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    currency: Mapped[str]   = mapped_column(String(3), nullable=False, default="XAF")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    discount_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    shipping_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    paid_cents: Mapped[int]  = mapped_column(BigInteger, default=0)
    refunded_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    purchase_order_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    client: Mapped[ClientModel] = relationship("ClientModel", back_populates="orders")
    items: Mapped[list[OrderItemModel]] = relationship(
        "OrderItemModel", back_populates="order", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[PaymentTransactionModel]] = relationship(
        "PaymentTransactionModel", back_populates="order"
    )

    @property
    def subtotal_cents(self) -> int:
        return sum(int(item.unit_price_cents * item.quantity) for item in self.items)

    @property
    def tax_cents(self) -> int:
        return int(self.subtotal_cents * self.tax_rate / 100)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.tax_cents - self.discount_cents + self.shipping_cents


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    item_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    delivered_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    invoiced_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="items")


# ─── Payments ──────────────────────────────────────────────────────────────────

class PaymentTransactionModel(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    transaction_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str]     = mapped_column(String(20), nullable=False, default="pending")
    method: Mapped[str]     = mapped_column(String(30), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str]   = mapped_column(String(3), nullable=False, default="XAF")
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    check_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    order: Mapped[OrderModel | None] = relationship("OrderModel", back_populates="transactions")


# ─── Refunds ───────────────────────────────────────────────────────────────────

class RefundModel(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    refund_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    original_transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"), nullable=False)
    refund_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_transactions.id"), nullable=True)
    status: Mapped[str]     = mapped_column(String(30), nullable=False, default="requested")
    reason: Mapped[str]     = mapped_column(String(50), nullable=False)
    reason_detail: Mapped[str] = mapped_column(Text, nullable=False)
    requested_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approved_amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str]   = mapped_column(String(3), nullable=False, default="XAF")
    method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ─── Products ──────────────────────────────────────────────────────────────────

class ProductModel(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    code: Mapped[str]      = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str]      = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None]       = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None]          = mapped_column(String(100), nullable=True, index=True)
    sub_category: Mapped[str | None]      = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None]              = mapped_column(String(20), nullable=True)
    currency: Mapped[str]  = mapped_column(String(3), nullable=False, default="XAF")
    unit_price_cents: Mapped[int]  = mapped_column(BigInteger, nullable=False, default=0)
    tax_rate: Mapped[Decimal]      = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    min_order_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("1"))
    track_stock: Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    stock_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    low_stock_threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str]    = mapped_column(String(20), nullable=False, default="active", index=True)
    notes: Mapped[str | None]     = mapped_column(Text, nullable=True)
    supplier_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None]   = mapped_column(String(60), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_deleted: Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ─── Permissions (RBAC granulaire) ────────────────────────────────────────────

class PermissionModel(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str]     = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RolePermissionModel(Base):
    __tablename__ = "role_permissions"

    role: Mapped[str]             = mapped_column(String(30), primary_key=True, nullable=False)
    permission_code: Mapped[str]  = mapped_column(
        ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    granted_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=_now)


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_type: Mapped[str]    = mapped_column(String(30), nullable=False)
    document_number: Mapped[str]  = mapped_column(String(60), unique=True, nullable=False, index=True)
    file_path: Mapped[str]        = mapped_column(String(500), nullable=False)
    file_name: Mapped[str]        = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str]        = mapped_column(String(100), nullable=False, default="application/pdf")
    is_signed: Mapped[bool]       = mapped_column(Boolean, default=False, nullable=False)
    is_stamped: Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    signed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    signed_at: Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    stamped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ocr_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    last_emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class DocumentType:
    PURCHASE_ORDER  = "purchase_order"
    PRO_FORMA       = "pro_forma"
    INVOICE         = "invoice"
    DELIVERY_NOTE   = "delivery_note"
    PAYMENT_RECEIPT = "payment_receipt"
    SCANNED         = "scanned"


# Alias pour compatibilité avec l'ancien code qui importait "Document"
Document = DocumentModel
User = UserModel


# ─── Audit log ─────────────────────────────────────────────────────────────────

class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
