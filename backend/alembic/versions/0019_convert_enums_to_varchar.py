"""convert enum columns to varchar

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-28
"""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users.role: userrole enum → varchar(30)
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(30) USING role::text")
    op.execute("DROP TYPE IF EXISTS userrole")

    # clients.client_type: clienttype enum → varchar(30)
    op.execute("ALTER TABLE clients ALTER COLUMN client_type TYPE VARCHAR(30) USING client_type::text")
    op.execute("DROP TYPE IF EXISTS clienttype")

    # orders.status + orders.payment_status
    op.execute("ALTER TABLE orders ALTER COLUMN status TYPE VARCHAR(30) USING status::text")
    op.execute("ALTER TABLE orders ALTER COLUMN payment_status TYPE VARCHAR(30) USING payment_status::text")
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS paymentstatus")


def downgrade() -> None:
    op.execute("""
        CREATE TYPE userrole AS ENUM ('super_admin','admin','manager','operator');
        ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole
    """)
    op.execute("""
        CREATE TYPE clienttype AS ENUM ('individual','company');
        ALTER TABLE clients ALTER COLUMN client_type TYPE clienttype USING client_type::clienttype
    """)
    op.execute("""
        CREATE TYPE orderstatus AS ENUM ('draft','confirmed','in_progress','delivered','cancelled','refunded');
        CREATE TYPE paymentstatus AS ENUM ('pending','partial','paid','overdue','refunded');
        ALTER TABLE orders ALTER COLUMN status TYPE orderstatus USING status::orderstatus;
        ALTER TABLE orders ALTER COLUMN payment_status TYPE paymentstatus USING payment_status::paymentstatus
    """)
