"""agent_credentials table

Revision ID: 20260530_0022
Revises: 20260530_0021
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260530_0022"
down_revision = "20260530_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_credentials_organization_id", "agent_credentials", ["organization_id"])
    op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])
    op.create_index("ix_agent_credentials_key_hash", "agent_credentials", ["key_hash"])


def downgrade() -> None:
    op.drop_index("ix_agent_credentials_key_hash", table_name="agent_credentials")
    op.drop_index("ix_agent_credentials_agent_id", table_name="agent_credentials")
    op.drop_index("ix_agent_credentials_organization_id", table_name="agent_credentials")
    op.drop_table("agent_credentials")
