"""Add deleted_by column to users table.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deleted_by", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_deleted_by",
        "users", "users",
        ["deleted_by"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_deleted_by", "users", type_="foreignkey")
    op.drop_column("users", "deleted_by")
