"""Fix schema drift — add missing columns to clients and orders tables.

Revision ID: 0022b
Revises: 0022
Create Date: 2026-06-18

Root cause:
  Several columns were added to the SQLAlchemy ORM models (clients, orders)
  without corresponding Alembic migrations. Any SELECT on these tables would
  fail with "column does not exist" → HTTP 500.

Changes:
  clients:
    - Rename address → address_line1 (ORM uses address_line1)
    - Add status       varchar(20)  DEFAULT 'active'
    - Add currency     varchar(3)   DEFAULT 'XAF'
    - Add credit_limit_cents   bigint DEFAULT 0
    - Add payment_terms_days   smallint DEFAULT 30
    - Add default_tax_rate     numeric(5,2) DEFAULT 0.00
    - Add deleted_by   uuid FK users.id

  orders:
    - Add purchase_order_ref  varchar(100) nullable
    - Add due_date             date nullable
    - Add confirmed_by         uuid FK users.id nullable
    - Add confirmed_at         timestamptz nullable
    - Add delivered_at         timestamptz nullable
    - Add cancelled_at         timestamptz nullable
    - Add cancelled_by         uuid FK users.id nullable
    - Add deleted_by           uuid FK users.id nullable

All operations are idempotent — safe on fresh databases where the column
already exists (created via create_all in tests) and on production databases
where the column is missing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "0022b"
down_revision = "0022"
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "  AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": col},
    )
    return r.fetchone() is not None


def _fk_exists(conn, name: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_type = 'FOREIGN KEY' AND constraint_name = :n"
        ),
        {"n": name},
    )
    return r.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # ── clients ───────────────────────────────────────────────────────────────

    # Rename address → address_line1
    if _col_exists(conn, "clients", "address") and not _col_exists(conn, "clients", "address_line1"):
        conn.execute(text("ALTER TABLE clients RENAME COLUMN address TO address_line1"))

    # Add address_line1 if neither form exists (fresh DB via create_all already has it)
    if not _col_exists(conn, "clients", "address_line1"):
        op.add_column("clients", sa.Column("address_line1", sa.String(255), nullable=True))

    if not _col_exists(conn, "clients", "status"):
        op.add_column(
            "clients",
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        )

    if not _col_exists(conn, "clients", "currency"):
        op.add_column(
            "clients",
            sa.Column("currency", sa.String(3), nullable=False, server_default="XAF"),
        )

    if not _col_exists(conn, "clients", "credit_limit_cents"):
        op.add_column(
            "clients",
            sa.Column("credit_limit_cents", sa.BigInteger(), nullable=False, server_default="0"),
        )

    if not _col_exists(conn, "clients", "payment_terms_days"):
        op.add_column(
            "clients",
            sa.Column("payment_terms_days", sa.SmallInteger(), nullable=False, server_default="30"),
        )

    if not _col_exists(conn, "clients", "default_tax_rate"):
        op.add_column(
            "clients",
            sa.Column("default_tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        )

    if not _col_exists(conn, "clients", "deleted_by"):
        op.add_column("clients", sa.Column("deleted_by", UUID(as_uuid=True), nullable=True))
        if not _fk_exists(conn, "fk_clients_deleted_by"):
            op.create_foreign_key(
                "fk_clients_deleted_by", "clients", "users", ["deleted_by"], ["id"]
            )

    # ── orders ────────────────────────────────────────────────────────────────

    if not _col_exists(conn, "orders", "purchase_order_ref"):
        op.add_column("orders", sa.Column("purchase_order_ref", sa.String(100), nullable=True))

    if not _col_exists(conn, "orders", "due_date"):
        op.add_column("orders", sa.Column("due_date", sa.Date(), nullable=True))

    if not _col_exists(conn, "orders", "confirmed_by"):
        op.add_column("orders", sa.Column("confirmed_by", UUID(as_uuid=True), nullable=True))
        if not _fk_exists(conn, "fk_orders_confirmed_by"):
            op.create_foreign_key(
                "fk_orders_confirmed_by", "orders", "users", ["confirmed_by"], ["id"]
            )

    if not _col_exists(conn, "orders", "confirmed_at"):
        op.add_column("orders", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))

    if not _col_exists(conn, "orders", "delivered_at"):
        op.add_column("orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))

    if not _col_exists(conn, "orders", "cancelled_at"):
        op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

    if not _col_exists(conn, "orders", "cancelled_by"):
        op.add_column("orders", sa.Column("cancelled_by", UUID(as_uuid=True), nullable=True))
        if not _fk_exists(conn, "fk_orders_cancelled_by"):
            op.create_foreign_key(
                "fk_orders_cancelled_by", "orders", "users", ["cancelled_by"], ["id"]
            )

    if not _col_exists(conn, "orders", "deleted_by"):
        op.add_column("orders", sa.Column("deleted_by", UUID(as_uuid=True), nullable=True))
        if not _fk_exists(conn, "fk_orders_deleted_by"):
            op.create_foreign_key(
                "fk_orders_deleted_by", "orders", "users", ["deleted_by"], ["id"]
            )


def downgrade() -> None:
    conn = op.get_bind()
    # orders — drop only if exists
    if _fk_exists(conn, "fk_orders_deleted_by"):
        op.drop_constraint("fk_orders_deleted_by", "orders", type_="foreignkey")
    if _col_exists(conn, "orders", "deleted_by"):
        op.drop_column("orders", "deleted_by")
    if _fk_exists(conn, "fk_orders_cancelled_by"):
        op.drop_constraint("fk_orders_cancelled_by", "orders", type_="foreignkey")
    if _col_exists(conn, "orders", "cancelled_by"):
        op.drop_column("orders", "cancelled_by")
    if _col_exists(conn, "orders", "cancelled_at"):
        op.drop_column("orders", "cancelled_at")
    if _col_exists(conn, "orders", "delivered_at"):
        op.drop_column("orders", "delivered_at")
    if _col_exists(conn, "orders", "confirmed_at"):
        op.drop_column("orders", "confirmed_at")
    if _fk_exists(conn, "fk_orders_confirmed_by"):
        op.drop_constraint("fk_orders_confirmed_by", "orders", type_="foreignkey")
    if _col_exists(conn, "orders", "confirmed_by"):
        op.drop_column("orders", "confirmed_by")
    if _col_exists(conn, "orders", "due_date"):
        op.drop_column("orders", "due_date")
    if _col_exists(conn, "orders", "purchase_order_ref"):
        op.drop_column("orders", "purchase_order_ref")
    # clients — drop only if exists
    if _fk_exists(conn, "fk_clients_deleted_by"):
        op.drop_constraint("fk_clients_deleted_by", "clients", type_="foreignkey")
    if _col_exists(conn, "clients", "deleted_by"):
        op.drop_column("clients", "deleted_by")
    if _col_exists(conn, "clients", "default_tax_rate"):
        op.drop_column("clients", "default_tax_rate")
    if _col_exists(conn, "clients", "payment_terms_days"):
        op.drop_column("clients", "payment_terms_days")
    if _col_exists(conn, "clients", "credit_limit_cents"):
        op.drop_column("clients", "credit_limit_cents")
    if _col_exists(conn, "clients", "currency"):
        op.drop_column("clients", "currency")
    if _col_exists(conn, "clients", "status"):
        op.drop_column("clients", "status")
    # Rename address_line1 → address only if it was renamed (not originally address_line1)
    if _col_exists(conn, "clients", "address_line1") and not _col_exists(conn, "clients", "address"):
        conn.execute(text("ALTER TABLE clients RENAME COLUMN address_line1 TO address"))
