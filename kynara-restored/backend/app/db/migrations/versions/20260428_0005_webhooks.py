"""Webhook subscriptions + outbox.

Revision ID: 20260428_0005
Revises: 0004_approval_requests
Create Date: 2026-04-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260428_0005"
down_revision = "0004_approval_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE webhook_outbox_status_enum AS ENUM "
        "('pending', 'delivered', 'failed', 'dead');"
    )

    op.create_table(
        "webhook_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("secret_hash", sa.String(128), nullable=False),
        sa.Column("secret_prefix", sa.String(16), nullable=False),
        sa.Column("event_types", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_webhook_endpoints_org", "webhook_endpoints", ["organization_id"])

    op.create_table(
        "webhook_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status",
                  postgresql.ENUM(name="webhook_outbox_status_enum", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deliver_after", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(2048)),
        sa.Column("last_response_status", sa.Integer),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_webhook_outbox_org", "webhook_outbox", ["organization_id"])
    op.create_index("ix_webhook_outbox_endpoint", "webhook_outbox", ["endpoint_id"])
    op.create_index("ix_webhook_outbox_status_time",
                    "webhook_outbox", ["status", "deliver_after"])

    # RLS
    for tbl in ("webhook_endpoints", "webhook_outbox"):
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY {tbl}_rls ON {tbl} USING "
            f"(organization_id = current_setting('app.org_id')::uuid);"
        )


def downgrade() -> None:
    op.drop_table("webhook_outbox")
    op.drop_table("webhook_endpoints")
    op.execute("DROP TYPE IF EXISTS webhook_outbox_status_enum;")
