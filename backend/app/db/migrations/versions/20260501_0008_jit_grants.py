"""Create jit_grants table — time-bound privilege elevations.

Revision ID: 20260501_0008
Revises: 20260501_0007
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260501_0008"
down_revision = "20260501_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jit_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "granted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        # The additional scopes this grant adds to the user's effective scope set.
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("ticket_url", sa.String(2048), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
        ),
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

    # Index for the expiry cron: finds active grants past their expiry fast.
    op.create_index(
        "ix_jit_grants_active_expiry",
        "jit_grants",
        ["is_active", "expires_at"],
    )

    # RLS — same pattern as all other tenant tables.
    op.execute("ALTER TABLE jit_grants ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY jit_grants_rls ON jit_grants "
        "USING (organization_id = current_setting('app.org_id')::uuid);"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS jit_grants_rls ON jit_grants;")
    op.drop_index("ix_jit_grants_active_expiry", table_name="jit_grants")
    op.drop_table("jit_grants")
