"""Production hardening — indexes + CHECK constraints

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-31

Changes:
  1. Index on users.reset_session_token — used in WHERE clause during password reset
     (full table scan on every reset attempt without it).
  2. Index on payment_transactions.transaction_date DESC — the journal list endpoint
     orders by this column; without an index it sorts the whole table every time.
  3. CHECK constraints — enforce business invariants at the DB layer so corrupt data
     can never enter regardless of application bugs:
       - order_items.quantity > 0
       - order_items.unit_price_cents >= 0
       - orders.discount_cents >= 0
       - orders.shipping_cents >= 0
       - orders.paid_cents >= 0
       - orders.refunded_cents >= 0
       - payment_transactions.amount_cents > 0
       - refunds.requested_amount_cents > 0
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Index users.reset_session_token ────────────────────────────────────
    # Only index non-null values — the column is NULL for most users at any time.
    op.create_index(
        "ix_users_reset_session_token",
        "users",
        ["reset_session_token"],
        postgresql_where=sa.text("reset_session_token IS NOT NULL"),
    )

    # ── 2. Index payment_transactions.transaction_date (DESC) ─────────────────
    op.create_index(
        "ix_payment_transactions_date_desc",
        "payment_transactions",
        [sa.text("transaction_date DESC")],
    )

    # ── 3. CHECK constraints — business invariants ────────────────────────────
    op.create_check_constraint(
        "ck_order_items_quantity_positive",
        "order_items",
        "quantity > 0",
    )
    op.create_check_constraint(
        "ck_order_items_unit_price_non_negative",
        "order_items",
        "unit_price_cents >= 0",
    )
    op.create_check_constraint(
        "ck_orders_discount_non_negative",
        "orders",
        "discount_cents >= 0",
    )
    op.create_check_constraint(
        "ck_orders_shipping_non_negative",
        "orders",
        "shipping_cents >= 0",
    )
    op.create_check_constraint(
        "ck_orders_paid_non_negative",
        "orders",
        "paid_cents >= 0",
    )
    op.create_check_constraint(
        "ck_orders_refunded_non_negative",
        "orders",
        "refunded_cents >= 0",
    )
    op.create_check_constraint(
        "ck_payment_transactions_amount_positive",
        "payment_transactions",
        "amount_cents > 0",
    )
    op.create_check_constraint(
        "ck_refunds_requested_amount_positive",
        "refunds",
        "requested_amount_cents > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_refunds_requested_amount_positive", "refunds", type_="check")
    op.drop_constraint("ck_payment_transactions_amount_positive", "payment_transactions", type_="check")
    op.drop_constraint("ck_orders_refunded_non_negative", "orders", type_="check")
    op.drop_constraint("ck_orders_paid_non_negative", "orders", type_="check")
    op.drop_constraint("ck_orders_shipping_non_negative", "orders", type_="check")
    op.drop_constraint("ck_orders_discount_non_negative", "orders", type_="check")
    op.drop_constraint("ck_order_items_unit_price_non_negative", "order_items", type_="check")
    op.drop_constraint("ck_order_items_quantity_positive", "order_items", type_="check")
    op.drop_index("ix_payment_transactions_date_desc", table_name="payment_transactions")
    op.drop_index("ix_users_reset_session_token", table_name="users")
