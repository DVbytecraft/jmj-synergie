"""Partial delivery and invoicing quantities on order items

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("delivered_quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "order_items",
        sa.Column("invoiced_quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("order_items", "invoiced_quantity")
    op.drop_column("order_items", "delivered_quantity")
