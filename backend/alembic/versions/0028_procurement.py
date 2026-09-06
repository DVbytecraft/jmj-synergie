"""Add suppliers and supplier purchase orders.

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("address_line1", sa.String(255)),
        sa.Column("tax_id", sa.String(60)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="XAF"),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "code", name="uq_suppliers_org_code"),
    )
    op.create_index("ix_suppliers_organization_id", "suppliers", ["organization_id"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("purchase_number", sa.String(40), nullable=False, unique=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="XAF"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("expected_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_purchase_orders_organization_id", "purchase_orders", ["organization_id"])
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_sales_order_id", "purchase_orders", ["sales_order_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    op.create_table(
        "purchase_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(20)),
        sa.Column("purchase_unit_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_purchase_order_items_purchase_order_id", "purchase_order_items", ["purchase_order_id"])
    op.create_index("ix_purchase_order_items_product_id", "purchase_order_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
    op.drop_table("suppliers")
