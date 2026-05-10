"""Add guardrail_rules table for threshold-based auto-revocation.

Revision ID: 20260502_0010
Revises:     20260501_0009
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "20260502_0010"
down_revision = "20260501_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guardrail_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("integration_id", UUID(as_uuid=True),
                  sa.ForeignKey("guardrail_integrations.id", ondelete="CASCADE"),
                  nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Threshold condition: fire when event_count events arrive within time_window_seconds
        sa.Column("event_count_threshold", sa.Integer, nullable=False, server_default="1"),
        sa.Column("time_window_seconds", sa.Integer, nullable=False, server_default="300"),
        # Optional filters — null means "match anything"
        sa.Column("filter_agent_ids", ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column("filter_severities", ARRAY(sa.String), nullable=True),
        sa.Column("filter_rule_names", ARRAY(sa.String), nullable=True),
        # Action to take when threshold is reached
        sa.Column("action", sa.String(80), nullable=False, server_default="alert_only"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # RLS: org isolation
    op.execute("ALTER TABLE guardrail_rules ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY guardrail_rules_org_isolation ON guardrail_rules
        USING (organization_id = current_setting('app.current_org_id', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS guardrail_rules_org_isolation ON guardrail_rules")
    op.drop_table("guardrail_rules")
