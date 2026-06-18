"""Issuer branding assets and colors

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("issuer_profiles", sa.Column("primary_color", sa.String(20), nullable=True))
    op.add_column("issuer_profiles", sa.Column("secondary_color", sa.String(20), nullable=True))
    op.add_column("issuer_profiles", sa.Column("font_family", sa.String(50), nullable=True))
    op.add_column("issuer_profiles", sa.Column("logo_path", sa.String(500), nullable=True))
    op.add_column("issuer_profiles", sa.Column("stamp_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("issuer_profiles", "stamp_path")
    op.drop_column("issuer_profiles", "logo_path")
    op.drop_column("issuer_profiles", "font_family")
    op.drop_column("issuer_profiles", "secondary_color")
    op.drop_column("issuer_profiles", "primary_color")
