"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # Users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("super_admin", "admin", "manager", "operator", name="userrole"), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("signature_path", sa.String(500), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Clients
    op.create_table(
        "clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("client_type", sa.Enum("individual", "company", name="clienttype"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("tax_id", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_clients_code", "clients", ["code"], unique=True)
    op.create_index("ix_clients_full_name", "clients", ["full_name"])

    # Orders
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("order_number", sa.String(30), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Enum("draft","confirmed","in_progress","delivered","cancelled","refunded", name="orderstatus"), nullable=False),
        sa.Column("payment_status", sa.Enum("pending","partial","paid","overdue","refunded", name="paymentstatus"), nullable=False),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False, default=0),
        sa.Column("tax_rate", sa.Numeric(5,2), nullable=False, default=0),
        sa.Column("tax_cents", sa.BigInteger(), nullable=False, default=0),
        sa.Column("discount_cents", sa.BigInteger(), nullable=False, default=0),
        sa.Column("total_cents", sa.BigInteger(), nullable=False, default=0),
        sa.Column("paid_cents", sa.BigInteger(), nullable=False, default=0),
        sa.Column("refunded_cents", sa.BigInteger(), nullable=False, default=0),
        sa.Column("currency", sa.String(3), nullable=False, default="XAF"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_client_id", "orders", ["client_id"])

    # Order items, payment_transactions, documents, audit_logs...
    # (abbreviated — full schema in models.py)


def downgrade() -> None:
    op.drop_table("orders")
    op.drop_table("clients")
    op.drop_table("users")
