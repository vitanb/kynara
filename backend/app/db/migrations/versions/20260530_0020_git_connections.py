"""git_connections table

Revision ID: 20260530_0020
Revises: 20260530_0019
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260530_0020"
down_revision = "20260530_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "git_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("repo_url", sa.String(1024), nullable=False),
        sa.Column("branch", sa.String(255), nullable=False, server_default="main"),
        sa.Column("access_token_enc", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("webhook_secret", sa.String(128), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_sha", sa.String(64), nullable=True),
        sa.Column("sync_status", sa.String(32), nullable=False, server_default="idle"),
        sa.Column("sync_error", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_git_connections_organization_id", "git_connections", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_git_connections_organization_id", table_name="git_connections")
    op.drop_table("git_connections")
