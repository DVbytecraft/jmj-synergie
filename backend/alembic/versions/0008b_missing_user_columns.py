"""Add missing user columns (status, is_email_verified, failed_login_count, locked_until)

Revision ID: 0008b
Revises: 0008
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0008b"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_cols = {col["name"] for col in sa.inspect(bind).get_columns("users")}

    if "status" not in existing_cols:
        op.add_column("users", sa.Column("status", sa.String(30), nullable=False, server_default="active"))

    if "is_email_verified" not in existing_cols:
        op.add_column("users", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    if "failed_login_count" not in existing_cols:
        op.add_column("users", sa.Column("failed_login_count", sa.SmallInteger(), nullable=False, server_default="0"))

    if "locked_until" not in existing_cols:
        op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "is_email_verified")
    op.drop_column("users", "status")
