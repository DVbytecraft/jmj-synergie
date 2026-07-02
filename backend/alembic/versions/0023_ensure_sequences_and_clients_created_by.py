"""Ensure sequences exist and clients.created_by is present.

Revision ID: 0023
Revises: 0022b
Create Date: 2026-06-18

Root cause:
  If the production DB was bootstrapped via SQLAlchemy create_all() + alembic stamp
  (instead of running migrations from 0001), then:
    - All ORM model columns exist (create_all creates them)
    - BUT sequences created in migrations 0012/0013/0016 do NOT exist
      because create_all() does not create sequences.
  Result: any INSERT that calls nextval('seq_client_code') etc. fails with
  "relation does not exist" ProgrammingError → HTTP 500.

  Also: clients.created_by was omitted from migration 0001 text (possibly edited
  after initial setup). Added here idempotently in case the column is missing.

Changes:
  Sequences (all idempotent via IF NOT EXISTS):
    - seq_client_code
    - seq_order_number
    - seq_refund_number
    - seq_txn_number
    - seq_invoice_number

  Clients table (all idempotent via _col_exists check):
    - created_by uuid FK → users.id
"""
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
import sqlalchemy as sa

revision = "0023"
down_revision = "0022b"
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "  AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": col},
    )
    return r.fetchone() is not None


def _fk_exists(conn, name: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_type = 'FOREIGN KEY' AND constraint_name = :n"
        ),
        {"n": name},
    )
    return r.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Sequences (idempotent — safe whether they exist or not) ───────────────
    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS seq_client_code  START 1 INCREMENT 1"))
    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS seq_order_number START 1 INCREMENT 1"))
    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS seq_refund_number START 1 INCREMENT 1"))
    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS seq_txn_number   START 1 INCREMENT 1"))
    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS seq_invoice_number START 1 INCREMENT 1"))

    # ── clients.created_by ────────────────────────────────────────────────────
    # Missing from migration 0001 text; may or may not exist on the live DB.
    if not _col_exists(conn, "clients", "created_by"):
        op.add_column(
            "clients",
            sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        )
        if not _fk_exists(conn, "fk_clients_created_by"):
            op.create_foreign_key(
                "fk_clients_created_by", "clients", "users", ["created_by"], ["id"]
            )


def downgrade() -> None:
    conn = op.get_bind()
    if _fk_exists(conn, "fk_clients_created_by"):
        op.drop_constraint("fk_clients_created_by", "clients", type_="foreignkey")
    if _col_exists(conn, "clients", "created_by"):
        op.drop_column("clients", "created_by")
    # Sequences: intentionally NOT dropped — data loss risk if rows exist.
