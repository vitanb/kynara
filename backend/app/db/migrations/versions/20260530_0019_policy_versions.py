"""policy_versions table

Revision ID: 20260530_0019
Revises: 20260530_0018
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260530_0019"
down_revision = "20260530_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot", postgresql.JSONB, nullable=False),
        sa.Column("changed_by", sa.String(128), nullable=False),
        sa.Column("change_note", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_pv_policy_version",
        "policy_versions",
        ["policy_id", "version_number"],
        unique=True,
    )
    op.create_index("ix_pv_org", "policy_versions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_pv_org", table_name="policy_versions")
    op.drop_index("ix_pv_policy_version", table_name="policy_versions")
    op.drop_table("policy_versions")
