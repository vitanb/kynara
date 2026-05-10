"""Create guardrail_integrations and guardrail_events tables.

Revision ID: 20260501_0009
Revises: 20260501_0008
Create Date: 2026-05-01
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260501_0009"
down_revision = "20260501_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum for providers ────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE guardrail_provider_enum AS ENUM
        ('arize', 'custom', 'langfuse', 'whylabs', 'fiddler')
    """)
    # ── Enum for actions on trigger ───────────────────────────────────────────
    op.execute("""
        CREATE TYPE guardrail_action_enum AS ENUM
        ('alert_only', 'suspend_agent', 'revoke_jit_grants',
         'deny_all_policy', 'reduce_to_readonly')
    """)

    # ── guardrail_integrations ────────────────────────────────────────────────
    op.create_table(
        "guardrail_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider", postgresql.ENUM(
            "arize","custom","langfuse","whylabs","fiddler",
            name="guardrail_provider_enum", create_type=False), nullable=False),
        # Inbound webhook secret – we verify HMAC on every inbound event
        sa.Column("webhook_secret_hash", sa.String(128), nullable=True),
        # For outbound calls to the provider (e.g. Arize API key)
        sa.Column("api_key_hash", sa.String(128), nullable=True),
        sa.Column("api_endpoint", sa.String(2048), nullable=True),
        # Default action when any guardrail in this integration fires
        sa.Column("default_action", postgresql.ENUM(
            "alert_only","suspend_agent","revoke_jit_grants",
            "deny_all_policy","reduce_to_readonly",
            name="guardrail_action_enum", create_type=False),
            nullable=False, server_default="alert_only"),
        # JSON map: severity_label → action override
        # e.g. {"critical": "suspend_agent", "warning": "alert_only"}
        sa.Column("severity_action_map", postgresql.JSONB, nullable=False,
                  server_default="{}"),
        # Optional: scope only to specific agents (null = all agents in org)
        sa.Column("agent_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=True),
        # Guardrail rule names to monitor (null = all rules)
        sa.Column("monitored_rules", postgresql.ARRAY(sa.String),
                  nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False,
                  server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE guardrail_integrations ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY guardrail_integrations_rls ON guardrail_integrations "
        "USING (organization_id = current_setting('app.org_id')::uuid);"
    )

    # ── guardrail_events ──────────────────────────────────────────────────────
    op.create_table(
        "guardrail_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("guardrail_integrations.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        # Raw provider-specific rule / check name
        sa.Column("rule_name", sa.String(400), nullable=False),
        sa.Column("severity", sa.String(80), nullable=False, server_default="warning"),
        # Full payload received from the provider
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        # What Kynara did in response
        sa.Column("action_taken", postgresql.ENUM(
            "alert_only","suspend_agent","revoke_jit_grants",
            "deny_all_policy","reduce_to_readonly",
            name="guardrail_action_enum", create_type=False), nullable=False),
        sa.Column("action_detail", postgresql.JSONB, nullable=False,
                  server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_guardrail_events_created",
                    "guardrail_events", ["organization_id", "created_at"])
    op.execute("ALTER TABLE guardrail_events ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY guardrail_events_rls ON guardrail_events "
        "USING (organization_id = current_setting('app.org_id')::uuid);"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS guardrail_events_rls ON guardrail_events;")
    op.execute("DROP POLICY IF EXISTS guardrail_integrations_rls ON guardrail_integrations;")
    op.drop_index("ix_guardrail_events_created", table_name="guardrail_events")
    op.drop_table("guardrail_events")
    op.drop_table("guardrail_integrations")
    op.execute("DROP TYPE IF EXISTS guardrail_action_enum;")
    op.execute("DROP TYPE IF EXISTS guardrail_provider_enum;")
