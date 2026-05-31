"""Production hardening — indexes + CHECK constraints

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-31

Changes:
  0. orders.shipping_cents — migration drift fix.
     The column was added to the SQLAlchemy model but no Alembic revision was
     ever written to create it in the database. Added conditionally here so the
     migration is safe on databases where the column exists (dev) and on those
     where it doesn't (fresh Render deployments).

  1. Index on users.reset_session_token (partial, non-null).
     The /reset-password endpoint queries: WHERE reset_session_token = :hash
     Without an index this is a full table scan on every call.

  2. Index on payment_transactions.transaction_date DESC.
     The journal list endpoint orders by this column for every page request.

  3. CHECK constraints — business invariants at the DB layer.
     Applied conditionally: only when the referenced column exists AND the
     constraint does not already exist. This makes the migration fully
     idempotent regardless of the database's prior state.

     order_items.quantity > 0
     order_items.unit_price_cents >= 0
     orders.discount_cents >= 0
     orders.shipping_cents >= 0
     orders.paid_cents >= 0
     orders.refunded_cents >= 0
     payment_transactions.amount_cents > 0
     refunds.requested_amount_cents > 0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _col_exists(conn, table: str, col: str) -> bool:
    """Return True if column exists in the public schema."""
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "  AND table_name = :t "
            "  AND column_name = :c"
        ),
        {"t": table, "c": col},
    )
    return r.fetchone() is not None


def _constraint_exists(conn, name: str) -> bool:
    """Return True if a table constraint with this name already exists."""
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = :n"
        ),
        {"n": name},
    )
    return r.fetchone() is not None


# ── Migration ─────────────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()

    # ── 0. Add missing columns ────────────────────────────────────────────────
    # orders.shipping_cents: in the SQLAlchemy model but never in a migration.
    if not _col_exists(conn, "orders", "shipping_cents"):
        op.add_column(
            "orders",
            sa.Column(
                "shipping_cents",
                sa.BigInteger(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )

    # ── 1. Indexes (CREATE INDEX IF NOT EXISTS — fully idempotent) ────────────
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_users_reset_session_token "
        "ON users(reset_session_token) "
        "WHERE reset_session_token IS NOT NULL"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_payment_transactions_date_desc "
        "ON payment_transactions(transaction_date DESC)"
    ))

    # ── 2. CHECK constraints ──────────────────────────────────────────────────
    # Each entry: (table, column, check_expression, constraint_name)
    # Skipped when: column doesn't exist OR constraint already exists.
    _checks = [
        ("order_items",          "quantity",               "quantity > 0",                 "ck_order_items_quantity_positive"),
        ("order_items",          "unit_price_cents",       "unit_price_cents >= 0",        "ck_order_items_unit_price_non_negative"),
        ("orders",               "discount_cents",         "discount_cents >= 0",          "ck_orders_discount_non_negative"),
        ("orders",               "shipping_cents",         "shipping_cents >= 0",          "ck_orders_shipping_non_negative"),
        ("orders",               "paid_cents",             "paid_cents >= 0",              "ck_orders_paid_non_negative"),
        ("orders",               "refunded_cents",         "refunded_cents >= 0",          "ck_orders_refunded_non_negative"),
        ("payment_transactions", "amount_cents",           "amount_cents > 0",             "ck_payment_transactions_amount_positive"),
        ("refunds",              "requested_amount_cents", "requested_amount_cents > 0",   "ck_refunds_requested_amount_positive"),
    ]

    for table, col, expr, constraint_name in _checks:
        if _col_exists(conn, table, col) and not _constraint_exists(conn, constraint_name):
            conn.execute(text(
                f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} CHECK ({expr})"
            ))


def downgrade() -> None:
    conn = op.get_bind()

    # Drop CHECK constraints (conditional — safe if they were never created)
    _constraints = [
        ("refunds",              "ck_refunds_requested_amount_positive"),
        ("payment_transactions", "ck_payment_transactions_amount_positive"),
        ("orders",               "ck_orders_refunded_non_negative"),
        ("orders",               "ck_orders_paid_non_negative"),
        ("orders",               "ck_orders_shipping_non_negative"),
        ("orders",               "ck_orders_discount_non_negative"),
        ("order_items",          "ck_order_items_unit_price_non_negative"),
        ("order_items",          "ck_order_items_quantity_positive"),
    ]
    for table, name in _constraints:
        if _constraint_exists(conn, name):
            conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))

    # Drop indexes
    conn.execute(text("DROP INDEX IF EXISTS ix_payment_transactions_date_desc"))
    conn.execute(text("DROP INDEX IF EXISTS ix_users_reset_session_token"))

    # NOTE: We intentionally do NOT drop orders.shipping_cents here.
    # If the column existed before this migration ran, dropping it would cause
    # data loss. Operators who need to roll back should handle it manually.
