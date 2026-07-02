"""Add missing indexes on frequently filtered status/date columns

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-02

Changes:
  Index on orders.status — filtered on every /orders list request.
  Index on orders.created_at — sorted/filtered on every /orders list request.
  Index on payment_transactions.status — filtered in payment_repository queries.
  Index on refunds.status — filtered in payment_repository queries.

  None of these columns had a dedicated index despite being filtered/sorted
  on effectively every request to their respective list endpoints — full
  table scans that grow linearly with table size.
"""
from alembic import op
from sqlalchemy import text

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders(created_at)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_payment_transactions_status "
        "ON payment_transactions(status)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_refunds_status ON refunds(status)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS ix_refunds_status"))
    conn.execute(text("DROP INDEX IF EXISTS ix_payment_transactions_status"))
    conn.execute(text("DROP INDEX IF EXISTS ix_orders_created_at"))
    conn.execute(text("DROP INDEX IF EXISTS ix_orders_status"))
