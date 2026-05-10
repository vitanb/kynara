"""password_reset_tokens table for forgot-password flow.

Revision ID: 0003_password_reset_tokens
Revises: 0002_org_invites
Create Date: 2026-04-26 00:01:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_password_reset_tokens"
down_revision = "0002_org_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 of the raw token — never store clear text
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_prt_user", "password_reset_tokens", ["user_id"])
    op.create_index("ix_prt_token", "password_reset_tokens", ["token_hash"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens CASCADE;")
