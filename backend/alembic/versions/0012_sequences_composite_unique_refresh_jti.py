"""Sequences, composite unique constraints, refresh_token_jti, last_emailed_at

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-27

Changes:
  1. PostgreSQL sequences for order numbers, client codes, refund numbers
     → eliminates COUNT(*)-based race conditions
  2. Drop global unique constraints on clients.code, clients.tax_id,
     products.code, products.barcode → replace with (organization_id, field)
     composite partial unique indexes
  3. Add users.refresh_token_jti (VARCHAR 36) for refresh token revocation
  4. Add documents.last_emailed_at (TIMESTAMPTZ) to prevent duplicate emails
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. PostgreSQL sequences ────────────────────────────────────────────────
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_client_code START 1 INCREMENT 1")
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_order_number START 1 INCREMENT 1")
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_refund_number START 1 INCREMENT 1")

    # ── 2. Composite unique indexes on clients ────────────────────────────────
    # Drop existing global unique constraints (may be index or constraint)
    op.execute("DROP INDEX IF EXISTS ix_clients_code")
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_code_key")
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_tax_id_key")
    op.execute("DROP INDEX IF EXISTS ix_clients_tax_id")

    # (organization_id, code) — partial: only when organization_id is not null
    op.create_index(
        "uq_clients_org_code",
        "clients",
        ["organization_id", "code"],
        unique=True,
        postgresql_where="organization_id IS NOT NULL",
    )
    # (organization_id, tax_id) — partial: only when both are set
    op.create_index(
        "uq_clients_org_tax_id",
        "clients",
        ["organization_id", "tax_id"],
        unique=True,
        postgresql_where="organization_id IS NOT NULL AND tax_id IS NOT NULL AND tax_id <> ''",
    )

    # ── 3. Composite unique indexes on products ───────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_products_code")
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_code_key")
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_barcode_key")
    op.execute("DROP INDEX IF EXISTS ix_products_barcode")

    op.create_index(
        "uq_products_org_code",
        "products",
        ["organization_id", "code"],
        unique=True,
        postgresql_where="organization_id IS NOT NULL",
    )
    op.create_index(
        "uq_products_org_barcode",
        "products",
        ["organization_id", "barcode"],
        unique=True,
        postgresql_where="organization_id IS NOT NULL AND barcode IS NOT NULL AND barcode <> ''",
    )

    # ── 4. users.refresh_token_jti ────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("refresh_token_jti", sa.String(36), nullable=True),
    )

    # ── 5. documents.last_emailed_at ──────────────────────────────────────────
    op.add_column(
        "documents",
        sa.Column("last_emailed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "last_emailed_at")
    op.drop_column("users", "refresh_token_jti")

    op.drop_index("uq_products_org_barcode", table_name="products")
    op.drop_index("uq_products_org_code", table_name="products")
    op.create_index("ix_products_code", "products", ["code"], unique=True)

    op.drop_index("uq_clients_org_tax_id", table_name="clients")
    op.drop_index("uq_clients_org_code", table_name="clients")
    op.create_index("ix_clients_code", "clients", ["code"], unique=True)

    op.execute("DROP SEQUENCE IF EXISTS seq_refund_number")
    op.execute("DROP SEQUENCE IF EXISTS seq_order_number")
    op.execute("DROP SEQUENCE IF EXISTS seq_client_code")
