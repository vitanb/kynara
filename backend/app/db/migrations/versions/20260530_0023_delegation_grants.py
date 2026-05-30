"""Agent-to-agent delegation grants table.

Revision ID: 20260530_0023
Revises: 20260530_0022
Create Date: 2026-05-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260530_0023"
down_revision = "20260530_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delegation_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("child_agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delegated_scopes", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("max_chain_depth", sa.Integer, nullable=False, server_default="1"),
        sa.Column("chain_depth", sa.Integer, nullable=False, server_default="1"),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_delegation_grants_org", "delegation_grants", ["organization_id"])
    op.create_index("ix_delegation_grants_parent", "delegation_grants", ["parent_agent_id"])
    op.create_index("ix_delegation_grants_child", "delegation_grants", ["child_agent_id"])


def downgrade() -> None:
    op.drop_index("ix_delegation_grants_child", "delegation_grants")
    op.drop_index("ix_delegation_grants_parent", "delegation_grants")
    op.drop_index("ix_delegation_grants_org", "delegation_grants")
    op.drop_table("delegation_grants")
