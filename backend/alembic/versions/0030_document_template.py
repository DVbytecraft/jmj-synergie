"""Add a selectable issuer document template.

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "issuer_profiles",
        sa.Column("document_template", sa.String(length=30), nullable=False, server_default="jmj_reference"),
    )


def downgrade() -> None:
    op.drop_column("issuer_profiles", "document_template")
