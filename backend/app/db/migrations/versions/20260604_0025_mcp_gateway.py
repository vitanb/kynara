"""Add mcp_servers and mcp_tools tables for the MCP authorization gateway.

Revision ID: 20260604_0025
Revises: 20260601_0024
Create Date: 2026-06-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260604_0025"
down_revision = "20260601_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("transport", sa.String(16), nullable=False, server_default="sse"),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("stdio_cmd", sa.String(2048), nullable=True),
        sa.Column("upstream_headers", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scope_prefix", sa.String(128), nullable=False, server_default="mcp"),
        sa.Column("fail_mode", sa.String(8), nullable=False, server_default="closed"),
        sa.Column("require_approval_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.String(40), nullable=True),
        sa.Column("tool_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "slug", name="uq_mcp_server_slug"),
    )

    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("server_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.String(4000), nullable=True),
        sa.Column("input_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scope", sa.String(256), nullable=False),
        sa.Column("risk_class", sa.String(16), nullable=False, server_default="low"),
        sa.Column("effect_override", sa.String(20), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("server_id", "name", name="uq_mcp_tool_name"),
    )


def downgrade() -> None:
    op.drop_table("mcp_tools")
    op.drop_table("mcp_servers")
