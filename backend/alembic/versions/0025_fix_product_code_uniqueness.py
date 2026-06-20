"""Drop global product code/barcode unique constraints — multi-tenant scope only.

The generate_code() function counts products per-org, but uq_products_code is
globally unique. In a multi-tenant setup Demo SARL takes PROD-00001, then
Synergie Pro also generates PROD-00001 → IntegrityError.

Fix: drop the global constraints and keep only the org-scoped ones
(uq_products_org_code, uq_products_org_barcode) which already exist.

Revision ID: 0025
Revises: 0024
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    constraints = {uc["name"] for uc in insp.get_unique_constraints("products")}

    if "uq_products_code" in constraints:
        op.drop_constraint("uq_products_code", "products", type_="unique")

    if "uq_products_barcode" in constraints:
        op.drop_constraint("uq_products_barcode", "products", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_products_code", "products", ["code"])
    op.create_unique_constraint("uq_products_barcode", "products", ["barcode"])
