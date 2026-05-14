"""Add approval_email column to policies table.

When a policy has effect='require_approval', operators can specify an email
address to notify when an approval request is triggered.  The column is
nullable — no email is sent when it is NULL.

Revision ID: 20260514_0017
Revises: 20260513_0016
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260514_0017"
down_revision = "20260513_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("approval_email", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("policies", "approval_email")
