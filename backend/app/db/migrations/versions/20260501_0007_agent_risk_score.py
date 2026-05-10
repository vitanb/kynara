"""Add risk_class, risk_score, risk_factors columns to agents table.

Revision ID: 20260501_0007
Revises: 20260428_0006
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260501_0007"
down_revision = "20260428_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE agent_risk_class_enum AS ENUM ('low', 'medium', 'high', 'critical');"
    )
    op.add_column(
        "agents",
        sa.Column(
            "risk_class",
            postgresql.ENUM(name="agent_risk_class_enum", create_type=False),
            nullable=False,
            server_default="medium",
        ),
    )
    op.add_column(
        "agents",
        sa.Column("risk_score", sa.Float, nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("risk_factors", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_agents_risk_score", "agents", ["risk_score"])


def downgrade() -> None:
    op.drop_index("ix_agents_risk_score", table_name="agents")
    op.drop_column("agents", "risk_factors")
    op.drop_column("agents", "risk_score")
    op.drop_column("agents", "risk_class")
    op.execute("DROP TYPE IF EXISTS agent_risk_class_enum;")
