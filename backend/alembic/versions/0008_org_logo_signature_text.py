"""Organisation logo, champs facture, signature texte utilisateur

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── OrganizationModel — champs nécessaires pour les factures ──────────────
    op.add_column("organizations", sa.Column("postal_code",   sa.String(20),  nullable=True))
    op.add_column("organizations", sa.Column("rccm",          sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("website",       sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("bank_name",     sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("bank_account",  sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("logo_url",      sa.String(500), nullable=True))

    # ── UserModel — signature texte (alternative à l'image) ───────────────────
    op.add_column("users", sa.Column("signature_text", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "signature_text")
    op.drop_column("organizations", "logo_url")
    op.drop_column("organizations", "bank_account")
    op.drop_column("organizations", "bank_name")
    op.drop_column("organizations", "website")
    op.drop_column("organizations", "rccm")
    op.drop_column("organizations", "postal_code")
