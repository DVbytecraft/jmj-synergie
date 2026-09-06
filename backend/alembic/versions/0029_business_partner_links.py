"""Link companies across customer, supplier and source-document roles.

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_suppliers_client_id_clients", "suppliers", "clients", ["client_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_suppliers_client_id", "suppliers", ["client_id"])
    op.create_unique_constraint("uq_suppliers_org_client", "suppliers", ["organization_id", "client_id"])

    op.add_column("purchase_orders", sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_purchase_orders_source_document", "purchase_orders", "documents", ["source_document_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_purchase_orders_source_document_id", "purchase_orders", ["source_document_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_orders_source_document_id", table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_source_document", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "source_document_id")
    op.drop_constraint("uq_suppliers_org_client", "suppliers", type_="unique")
    op.drop_index("ix_suppliers_client_id", table_name="suppliers")
    op.drop_constraint("fk_suppliers_client_id_clients", "suppliers", type_="foreignkey")
    op.drop_column("suppliers", "client_id")
