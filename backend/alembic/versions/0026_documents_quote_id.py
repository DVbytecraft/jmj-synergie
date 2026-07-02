"""Add documents.quote_id — devis PDF generation never persisted a Document row.

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-01

Root cause:
  PDFService.generate_quote() built the PDF file but returned a bare path
  instead of a Document row (unlike every sibling generate_* method), and
  the /documents/quote/{id} endpoint expected a Document back — any devis
  PDF preview/generation crashed with a 500. There was also no column to
  link a Document to its originating quote.
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("quote_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("quotes.id"), nullable=True),
    )
    op.create_index("ix_documents_quote_id", "documents", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_quote_id", table_name="documents")
    op.drop_column("documents", "quote_id")
