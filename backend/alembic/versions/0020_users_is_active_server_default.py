"""Add server default true to users.is_active

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-28
"""
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT true")
    op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")
