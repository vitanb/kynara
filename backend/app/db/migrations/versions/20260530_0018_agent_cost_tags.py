"""Agent cost-attribution tags: project, team, cost_centre.

Revision ID: 20260530_0018
Revises: 20260527_0013
Create Date: 2026-05-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260530_0018"
down_revision = "20260527_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("project", sa.String(128), nullable=True))
    op.add_column("agents", sa.Column("team", sa.String(128), nullable=True))
    op.add_column("agents", sa.Column("cost_centre", sa.String(128), nullable=True))
    op.create_index("ix_agents_project", "agents", ["project"])
    op.create_index("ix_agents_team", "agents", ["team"])
    op.create_index("ix_agents_cost_centre", "agents", ["cost_centre"])


def downgrade() -> None:
    op.drop_index("ix_agents_cost_centre", table_name="agents")
    op.drop_index("ix_agents_team", table_name="agents")
    op.drop_index("ix_agents_project", table_name="agents")
    op.drop_column("agents", "cost_centre")
    op.drop_column("agents", "team")
    op.drop_column("agents", "project")
