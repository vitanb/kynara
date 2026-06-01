"""Add org_integrations table for per-org Slack/Teams/PagerDuty config.

Revision ID: 20260601_0024
Revises: 20260530_0023
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260601_0024"
down_revision = "20260530_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_integrations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False, unique=True, index=True),

        # Slack — bot token path (interactive buttons)
        sa.Column("slack_bot_token_enc", sa.Text, nullable=True),
        sa.Column("slack_signing_secret_enc", sa.Text, nullable=True),
        sa.Column("slack_channel_id", sa.String(64), nullable=True),
        # Slack — incoming webhook path (simpler)
        sa.Column("slack_webhook_url_enc", sa.Text, nullable=True),
        sa.Column("slack_enabled", sa.Boolean, nullable=False, server_default=sa.false()),

        # Microsoft Teams
        sa.Column("teams_webhook_url_enc", sa.Text, nullable=True),
        sa.Column("teams_callback_secret_enc", sa.Text, nullable=True),
        sa.Column("teams_enabled", sa.Boolean, nullable=False, server_default=sa.false()),

        # PagerDuty
        sa.Column("pagerduty_routing_key_enc", sa.Text, nullable=True),
        sa.Column("pagerduty_enabled", sa.Boolean, nullable=False, server_default=sa.false()),

        # Email notifications
        sa.Column("approval_email_to", sa.Text, nullable=True),  # comma-separated
        sa.Column("approval_email_enabled", sa.Boolean, nullable=False, server_default=sa.false()),

        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("org_integrations")
