"""approval_requests table — stores pending human-approval decisions.

Revision ID: 0004_approval_requests
Revises: 0003_password_reset_tokens
Create Date: 2026-04-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_approval_requests"
down_revision = "0003_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE approval_status_enum AS ENUM "
        "('pending','approved','rejected','expired'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))

    approval_status = postgresql.ENUM(name="approval_status_enum", create_type=False)

    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),

        # What was being requested
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id",   sa.String(128), nullable=False),
        sa.Column("on_behalf_of_user_id", sa.String(128), nullable=True),
        sa.Column("action",        sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=True),
        sa.Column("resource_id",   sa.String(255), nullable=True),
        sa.Column("resource_attrs", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("context",       postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("matched_policy_id", sa.String(128), nullable=True),

        # Review
        sa.Column("status", approval_status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note",   sa.String(1024), nullable=True),

        # Lifecycle
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approval_org_status",
                    "approval_requests", ["organization_id", "status"])
    op.create_index("ix_approval_subject",
                    "approval_requests", ["subject_type", "subject_id"])


def downgrade() -> None:
    op.drop_table("approval_requests")
    op.execute("DROP TYPE IF EXISTS approval_status_enum;")
