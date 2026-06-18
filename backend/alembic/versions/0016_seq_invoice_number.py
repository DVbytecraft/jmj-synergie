"""Create seq_invoice_number sequence.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-28
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_invoice_number START 1 INCREMENT 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS seq_invoice_number")
