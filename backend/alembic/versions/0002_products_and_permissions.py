"""Products catalogue and granular RBAC permissions

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# ── Default permissions seed data ─────────────────────────────────────────────

_PERMISSIONS = [
    ("clients:read",        "Consulter les clients",               "clients"),
    ("clients:create",      "Créer des clients",                   "clients"),
    ("clients:update",      "Modifier les clients",                "clients"),
    ("clients:delete",      "Supprimer des clients",               "clients"),
    ("orders:read",         "Consulter les commandes",             "orders"),
    ("orders:create",       "Créer des commandes",                 "orders"),
    ("orders:update",       "Modifier des commandes (draft)",      "orders"),
    ("orders:confirm",      "Confirmer des commandes",             "orders"),
    ("orders:cancel",       "Annuler des commandes",               "orders"),
    ("orders:delete",       "Supprimer des commandes",             "orders"),
    ("products:read",       "Consulter le catalogue produits",     "products"),
    ("products:create",     "Créer des produits",                  "products"),
    ("products:update",     "Modifier des produits",               "products"),
    ("products:delete",     "Supprimer des produits",              "products"),
    ("payments:read",       "Consulter les paiements",             "payments"),
    ("payments:record",     "Enregistrer un paiement",             "payments"),
    ("refunds:read",        "Consulter les remboursements",        "refunds"),
    ("refunds:request",     "Demander un remboursement",           "refunds"),
    ("refunds:approve",     "Approuver un remboursement",          "refunds"),
    ("refunds:reject",      "Rejeter un remboursement",            "refunds"),
    ("documents:read",      "Consulter les documents",             "documents"),
    ("documents:generate",  "Générer des PDF",                     "documents"),
    ("documents:upload",    "Uploader des fichiers",               "documents"),
    ("documents:delete",    "Supprimer des documents",             "documents"),
    ("users:read",          "Consulter les utilisateurs",          "users"),
    ("users:create",        "Créer des utilisateurs",              "users"),
    ("users:update",        "Modifier les utilisateurs",           "users"),
    ("users:delete",        "Désactiver des utilisateurs",         "users"),
    ("permissions:read",    "Consulter les permissions",           "permissions"),
    ("permissions:manage",  "Gérer les permissions par rôle",      "permissions"),
]

_ROLE_PERMISSIONS = {
    "manager": [
        "clients:read", "clients:create", "clients:update",
        "orders:read", "orders:create", "orders:update", "orders:confirm", "orders:cancel",
        "products:read", "products:create", "products:update",
        "payments:read", "payments:record",
        "refunds:read", "refunds:request", "refunds:approve", "refunds:reject",
        "documents:read", "documents:generate", "documents:upload",
        "users:read",
    ],
    "operator": [
        "clients:read",
        "orders:read", "orders:create", "orders:update",
        "products:read",
        "payments:read",
        "refunds:read", "refunds:request",
        "documents:read", "documents:upload",
    ],
}


def upgrade() -> None:
    # ── products table ─────────────────────────────────────────────────────────
    op.execute("CREATE TYPE product_status AS ENUM ('active','inactive','discontinued','draft')")

    op.create_table(
        "products",
        sa.Column("id",               UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code",             sa.String(50),  nullable=False),
        sa.Column("name",             sa.String(255), nullable=False),
        sa.Column("description",      sa.Text,        nullable=True),
        sa.Column("short_description",sa.String(500), nullable=True),
        sa.Column("category",         sa.String(100), nullable=True),
        sa.Column("sub_category",     sa.String(100), nullable=True),
        sa.Column("unit",             sa.String(20),  nullable=True),
        sa.Column("currency",         sa.String(3),   nullable=False, server_default="XAF"),
        sa.Column("unit_price_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_rate",         sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("min_order_quantity", sa.Numeric(14, 4), nullable=False, server_default="1"),
        sa.Column("track_stock",      sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("stock_quantity",   sa.Numeric(14, 4), nullable=True),
        sa.Column("low_stock_threshold", sa.Numeric(14, 4), nullable=True),
        sa.Column("image_path",       sa.String(500), nullable=True),
        sa.Column("status",           sa.String(20),  nullable=False, server_default="active"),
        sa.Column("notes",            sa.Text,        nullable=True),
        sa.Column("supplier_ref",     sa.String(100), nullable=True),
        sa.Column("barcode",          sa.String(60),  nullable=True),
        sa.Column("created_by",       UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_deleted",       sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("deleted_at",       sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code",    name="uq_products_code"),
        sa.UniqueConstraint("barcode", name="uq_products_barcode"),
    )
    op.create_index("idx_products_code",     "products", ["code"])
    op.create_index("idx_products_name",     "products", ["name"])
    op.create_index("idx_products_category", "products", ["category"])
    op.create_index("idx_products_status",   "products", ["status"])

    # ── permissions table ──────────────────────────────────────────────────────
    op.create_table(
        "permissions",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code",        sa.String(100), nullable=False),
        sa.Column("description", sa.Text,        nullable=True),
        sa.Column("category",    sa.String(50),  nullable=False, server_default="general"),
        sa.Column("is_active",   sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )

    # ── role_permissions table ─────────────────────────────────────────────────
    op.create_table(
        "role_permissions",
        sa.Column("role",            sa.String(30),  nullable=False),
        sa.Column("permission_code", sa.String(100), sa.ForeignKey("permissions.code", ondelete="CASCADE"), nullable=False),
        sa.Column("granted_by",      UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("granted_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("role", "permission_code"),
    )
    op.create_index("idx_role_perms_role", "role_permissions", ["role"])

    # ── Seed permissions ──────────────────────────────────────────────────────
    permissions_table = sa.table(
        "permissions",
        sa.column("code",        sa.String),
        sa.column("description", sa.String),
        sa.column("category",    sa.String),
    )
    op.bulk_insert(permissions_table, [
        {"code": code, "description": desc, "category": cat}
        for code, desc, cat in _PERMISSIONS
    ])

    # ── Seed role_permissions ─────────────────────────────────────────────────
    role_perms_table = sa.table(
        "role_permissions",
        sa.column("role",            sa.String),
        sa.column("permission_code", sa.String),
    )
    # super_admin et admin : toutes les permissions
    all_codes = [p[0] for p in _PERMISSIONS]
    admin_codes = [c for c in all_codes if c != "permissions:manage"]

    rows = (
        [{"role": "super_admin", "permission_code": c} for c in all_codes]
        + [{"role": "admin",      "permission_code": c} for c in admin_codes]
        + [{"role": r, "permission_code": c} for r, codes in _ROLE_PERMISSIONS.items() for c in codes]
    )
    op.bulk_insert(role_perms_table, rows)


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_index("idx_products_status",   "products")
    op.drop_index("idx_products_category", "products")
    op.drop_index("idx_products_name",     "products")
    op.drop_index("idx_products_code",     "products")
    op.drop_table("products")
    op.execute("DROP TYPE IF EXISTS product_status")
