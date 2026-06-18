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
    # users.is_active does not exist — users use the 'status' varchar column.
    # organizations.is_active already has a server default.
    # This migration is a no-op kept only for revision continuity.
    pass


def downgrade() -> None:
    pass
