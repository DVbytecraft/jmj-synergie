"""Convert quantity columns from NUMERIC(14,4) to INTEGER.

Quantities in order_items and products represent whole units — no fractional
quantities are used in this domain. Converting to INTEGER enforces this at the
DB level, eliminates implicit decimal rounding bugs, and simplifies all
arithmetic in application code.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── order_items ───────────────────────────────────────────────────────────
    # Truncate any fractional values that may exist before cast
    op.execute("""
        ALTER TABLE order_items
            ALTER COLUMN quantity           TYPE INTEGER USING quantity::integer,
            ALTER COLUMN delivered_quantity TYPE INTEGER USING delivered_quantity::integer,
            ALTER COLUMN invoiced_quantity  TYPE INTEGER USING invoiced_quantity::integer
    """)

    # ── products ──────────────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE products
            ALTER COLUMN min_order_quantity   TYPE INTEGER USING min_order_quantity::integer,
            ALTER COLUMN stock_quantity       TYPE INTEGER USING COALESCE(stock_quantity::integer, NULL),
            ALTER COLUMN low_stock_threshold  TYPE INTEGER USING COALESCE(low_stock_threshold::integer, NULL)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE order_items
            ALTER COLUMN quantity           TYPE NUMERIC(14,4) USING quantity::numeric,
            ALTER COLUMN delivered_quantity TYPE NUMERIC(14,4) USING delivered_quantity::numeric,
            ALTER COLUMN invoiced_quantity  TYPE NUMERIC(14,4) USING invoiced_quantity::numeric
    """)
    op.execute("""
        ALTER TABLE products
            ALTER COLUMN min_order_quantity   TYPE NUMERIC(14,4) USING min_order_quantity::numeric,
            ALTER COLUMN stock_quantity       TYPE NUMERIC(14,4) USING stock_quantity::numeric,
            ALTER COLUMN low_stock_threshold  TYPE NUMERIC(14,4) USING low_stock_threshold::numeric
    """)
