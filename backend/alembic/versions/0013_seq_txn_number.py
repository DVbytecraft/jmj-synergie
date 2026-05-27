"""Add seq_txn_number sequence for collision-free transaction numbers.

Revision ID: 0013
Revises: 0012
Create Date: 2025-05-27
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_txn_number START 1 INCREMENT 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS seq_txn_number")
