"""Add agent_identity_providers + agents.external_source/external_id for Okta sync.

Revision ID: 20260605_0026
Revises: 20260604_0025
Create Date: 2026-06-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260605_0026"
down_revision = "20260604_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("external_source", sa.String(32), nullable=True))
    op.add_column("agents", sa.Column("external_id", sa.String(128), nullable=True))
    op.create_index("ix_agents_external_source", "agents", ["external_source"])
    op.create_index("ix_agents_external_id", "agents", ["external_id"])

    op.create_table(
        "agent_identity_providers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="okta"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_token_enc", sa.String(4096), nullable=True),
        sa.Column("sync_mode", sa.String(16), nullable=False, server_default="agents"),
        sa.Column("group_id", sa.String(64), nullable=True),
        sa.Column("default_mode", sa.String(24), nullable=False, server_default="human_supervised"),
        sa.Column("role_mapping", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("default_on_behalf_user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deactivate_missing", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.String(40), nullable=True),
        sa.Column("last_sync_status", sa.String(16), nullable=True),
        sa.Column("last_sync_stats", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("agent_identity_providers")
    op.drop_index("ix_agents_external_id", table_name="agents")
    op.drop_index("ix_agents_external_source", table_name="agents")
    op.drop_column("agents", "external_id")
    op.drop_column("agents", "external_source")
