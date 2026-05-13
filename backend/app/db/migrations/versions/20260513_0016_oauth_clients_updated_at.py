"""Add missing updated_at column to oauth_clients table.

OAuthClient extends TimestampMixin which maps updated_at, but migration
20260512_0014 only created created_at.  This caused every SELECT on
oauth_clients (including GET /oauth/authorize) to raise a column-not-found
error → 500 Internal Server Error.

Revision ID: 20260513_0016
Revises: 20260513_0015
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260513_0016"
down_revision = "20260513_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add updated_at — backfill existing rows with created_at value,
    # then set a server default + trigger so it updates on every write.
    op.add_column(
        "oauth_clients",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("oauth_clients", "updated_at")
