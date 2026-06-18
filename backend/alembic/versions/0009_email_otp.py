"""OTP vérification email — champs sur UserModel

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_otp_hash",       sa.String(128), nullable=True))
    op.add_column("users", sa.Column("email_otp_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("email_otp_attempts",   sa.SmallInteger(), nullable=False, server_default="0"))

    # Tous les utilisateurs existants sont considérés vérifiés (antérieurs à l'OTP)
    op.execute("UPDATE users SET is_email_verified = TRUE WHERE is_email_verified = FALSE")


def downgrade() -> None:
    op.drop_column("users", "email_otp_attempts")
    op.drop_column("users", "email_otp_expires_at")
    op.drop_column("users", "email_otp_hash")
