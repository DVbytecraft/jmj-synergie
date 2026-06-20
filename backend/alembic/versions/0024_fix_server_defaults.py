"""Fix missing server_default on users.is_active and orders totals columns.

users.is_active        : NOT NULL, no server_default → add DEFAULT true
orders.subtotal_cents  : NOT NULL, no server_default → add DEFAULT 0
orders.tax_cents       : NOT NULL, no server_default → add DEFAULT 0
orders.total_cents     : NOT NULL, no server_default → add DEFAULT 0

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_users = {col["name"] for col in sa.inspect(bind).get_columns("users")}
    existing_orders = {col["name"] for col in sa.inspect(bind).get_columns("orders")}

    # users.is_active — add server_default true (column exists, just missing default)
    if "is_active" in existing_users:
        op.alter_column(
            "users", "is_active",
            server_default=sa.text("true"),
            existing_type=sa.Boolean(),
            existing_nullable=False,
        )

    # orders — add server_default 0 to computed-total columns
    for col in ("subtotal_cents", "tax_cents", "total_cents"):
        if col in existing_orders:
            op.alter_column(
                "orders", col,
                server_default=sa.text("0"),
                existing_type=sa.BigInteger(),
                existing_nullable=False,
            )


def downgrade() -> None:
    for col in ("subtotal_cents", "tax_cents", "total_cents"):
        op.alter_column("orders", col, server_default=None,
                        existing_type=sa.BigInteger(), existing_nullable=False)
    op.alter_column("users", "is_active", server_default=None,
                    existing_type=sa.Boolean(), existing_nullable=False)
