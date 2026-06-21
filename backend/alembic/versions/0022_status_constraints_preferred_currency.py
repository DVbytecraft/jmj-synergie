"""status CHECK constraints + preferred_currency on organizations

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Users: enforce valid status values ────────────────────────────────────
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT ck_users_status
        CHECK (status IN ('active', 'inactive', 'suspended', 'pending'))
    """)

    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT ck_users_role
        CHECK (role IN ('super_admin', 'admin', 'manager', 'operator'))
    """)

    # ── Organizations: preferred currency ─────────────────────────────────────
    op.add_column(
        "organizations",
        sa.Column("preferred_currency", sa.String(10), nullable=False, server_default="XAF"),
    )

    # ── Products: stock management columns ────────────────────────────────────
    op.add_column("products", sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("stock_alert_threshold", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("track_stock", sa.Boolean(), nullable=False, server_default="false"))

    op.execute("""
        ALTER TABLE products
        ADD CONSTRAINT ck_products_stock_quantity CHECK (stock_quantity >= 0)
    """)
    op.execute("""
        ALTER TABLE products
        ADD CONSTRAINT ck_products_stock_alert CHECK (stock_alert_threshold >= 0)
    """)

    # ── Quotes table ──────────────────────────────────────────────────────────
    op.create_table(
        "quotes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("quote_number", sa.String(30), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="XAF"),
        sa.Column("subtotal_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("tax_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_to_order_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )

    op.execute("""
        ALTER TABLE quotes
        ADD CONSTRAINT ck_quotes_status
        CHECK (status IN ('draft', 'sent', 'accepted', 'rejected', 'expired', 'converted'))
    """)
    op.execute("ALTER TABLE quotes ADD CONSTRAINT ck_quotes_subtotal CHECK (subtotal_cents >= 0)")
    op.execute("ALTER TABLE quotes ADD CONSTRAINT ck_quotes_total CHECK (total_cents >= 0)")

    op.create_index("ix_quotes_organization_id", "quotes", ["organization_id"])
    op.create_index("ix_quotes_client_id", "quotes", ["client_id"])
    op.create_index("ix_quotes_status", "quotes", ["status"])

    # ── Quote items table ─────────────────────────────────────────────────────
    op.create_table(
        "quote_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quote_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False, server_default="0"),
    )

    op.execute("ALTER TABLE quote_items ADD CONSTRAINT ck_quote_items_qty CHECK (quantity > 0)")
    op.execute("ALTER TABLE quote_items ADD CONSTRAINT ck_quote_items_price CHECK (unit_price_cents >= 0)")
    op.execute("ALTER TABLE quote_items ADD CONSTRAINT ck_quote_items_total CHECK (total_cents >= 0)")

    # ── Quote sequence ────────────────────────────────────────────────────────
    op.execute("CREATE SEQUENCE IF NOT EXISTS quote_number_seq START 1 INCREMENT 1")

    # ── Client portal tokens ──────────────────────────────────────────────────
    op.create_table(
        "client_portal_tokens",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )

    op.create_index("ix_portal_tokens_token_hash", "client_portal_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_table("client_portal_tokens")
    op.drop_table("quote_items")
    op.drop_table("quotes")
    op.execute("DROP SEQUENCE IF EXISTS quote_number_seq")
    op.drop_column("products", "track_stock")
    op.drop_column("products", "stock_alert_threshold")
    op.drop_column("products", "stock_quantity")
    op.drop_column("organizations", "preferred_currency")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_status")
