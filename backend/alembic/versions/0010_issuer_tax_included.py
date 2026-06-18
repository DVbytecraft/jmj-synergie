"""IssuerProfile — champ tax_included (TVA incluse ou hors taxe)

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "issuer_profiles",
        sa.Column("tax_included", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("issuer_profiles", "tax_included")
