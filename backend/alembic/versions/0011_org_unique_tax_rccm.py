"""Organizations — index partiels uniques sur tax_id et rccm

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-20
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unicité partielle : deux organisations ne peuvent pas avoir le même NIF
    # (seulement quand tax_id est renseigné et non vide)
    op.create_index(
        "ix_organizations_tax_id_unique",
        "organizations",
        ["tax_id"],
        unique=True,
        postgresql_where="tax_id IS NOT NULL AND tax_id <> ''",
    )
    # Unicité partielle : deux organisations ne peuvent pas avoir le même RCCM
    op.create_index(
        "ix_organizations_rccm_unique",
        "organizations",
        ["rccm"],
        unique=True,
        postgresql_where="rccm IS NOT NULL AND rccm <> ''",
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_rccm_unique", table_name="organizations")
    op.drop_index("ix_organizations_tax_id_unique", table_name="organizations")
