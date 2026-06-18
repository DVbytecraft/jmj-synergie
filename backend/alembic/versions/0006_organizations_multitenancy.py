"""Organizations and tenant scoping

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text
import uuid

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("tax_id", sa.String(60), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_organizations_code"),
    )

    for table in ["users", "issuer_profiles", "clients", "orders", "payment_transactions", "refunds", "products", "documents"]:
        op.add_column(table, sa.Column("organization_id", UUID(as_uuid=True), nullable=True))
        op.create_index(f"idx_{table}_organization_id", table, ["organization_id"])
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
        )

    conn = op.get_bind()
    users = conn.execute(text("SELECT id, full_name, email FROM users")).fetchall()
    for user in users:
        org_id = uuid.uuid4()
        code = f"ORG-{str(user.id).replace('-', '')[:10].upper()}"
        name = user.full_name or user.email or "Organisation"
        conn.execute(
            text("INSERT INTO organizations (id, code, name, email) VALUES (:id, :code, :name, :email)"),
            {"id": org_id, "code": code, "name": name, "email": user.email},
        )
        conn.execute(text("UPDATE users SET organization_id = :org_id WHERE id = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE issuer_profiles SET organization_id = :org_id WHERE user_id = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE clients SET organization_id = :org_id WHERE created_by = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE orders SET organization_id = :org_id WHERE created_by = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE products SET organization_id = :org_id WHERE created_by = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE documents SET organization_id = :org_id WHERE created_by = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE payment_transactions SET organization_id = :org_id WHERE recorded_by = :user_id"), {"org_id": org_id, "user_id": user.id})
        conn.execute(text("UPDATE refunds SET organization_id = :org_id WHERE requested_by = :user_id"), {"org_id": org_id, "user_id": user.id})


def downgrade() -> None:
    for table in ["documents", "products", "refunds", "payment_transactions", "orders", "clients", "issuer_profiles", "users"]:
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_index(f"idx_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")
    op.drop_table("organizations")
