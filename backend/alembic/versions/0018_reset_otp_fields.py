"""Add OTP-based password reset fields to users table.

Replaces the link-based reset flow with a 3-step OTP flow:
  1. forgot-password → generates 6-digit OTP, stored hashed in password_reset_token
  2. verify-reset-otp → validates OTP, stores short-lived session token hash
  3. reset-password  → validates session token, sets new password

New fields:
  reset_otp_attempts       — brute-force counter (max 5 attempts)
  reset_session_token      — SHA-256 hash of the session token issued after OTP verified
  reset_session_expires_at — 10-minute TTL on the session token

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "reset_otp_attempts",
        sa.SmallInteger(),
        nullable=False,
        server_default="0",
    ))
    op.add_column("users", sa.Column(
        "reset_session_token",
        sa.String(128),
        nullable=True,
    ))
    op.add_column("users", sa.Column(
        "reset_session_expires_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("users", "reset_session_expires_at")
    op.drop_column("users", "reset_session_token")
    op.drop_column("users", "reset_otp_attempts")
