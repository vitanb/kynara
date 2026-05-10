"""Add is_superadmin to users; promote vitanreddy@gmail.com.

Revision ID: 0012_superadmin
Revises: 0011_user_profile
Create Date: 2026-05-05
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "20260505_0012"
down_revision = "20260504_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "is_superadmin", sa.Boolean(), nullable=False, server_default="false"
    ))

    # Promote the platform owner account
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE users SET is_superadmin = true WHERE email = :email"),
        {"email": "vitanreddy@gmail.com"},
    )


def downgrade() -> None:
    op.drop_column("users", "is_superadmin")
