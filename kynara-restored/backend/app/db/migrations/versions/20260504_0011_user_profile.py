"""Add timezone and avatar_url to users table for profile customisation.

Revision ID: 20260504_0011
Revises:     20260502_0010
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260504_0011"
down_revision = "20260502_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("timezone", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "timezone")
