"""BYOK + data residency: per-tenant KMS key ARNs and region pinning.

Revision ID: 20260428_0006
Revises: 20260428_0005
Create Date: 2026-04-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260428_0006"
down_revision = "20260428_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Allowed values: 'us-east-1', 'us-west-2', 'eu-west-1', 'eu-central-1', 'ap-southeast-2'
    op.add_column("organizations",
        sa.Column("region", sa.String(32), nullable=False, server_default="us-east-1"))
    op.add_column("organizations",
        sa.Column("residency_strict", sa.Boolean, nullable=False, server_default=sa.false()))

    op.create_table(
        "tenant_keys",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("kms_key_arn", sa.String(2048)),
        sa.Column("kms_key_alias", sa.String(255)),
        sa.Column("kind", sa.String(32), nullable=False, server_default="platform"),
        # 'platform' (Kynara-managed) or 'byok' (customer KMS via grant)
        sa.Column("rotation_period_days", sa.Integer, server_default="365"),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE tenant_keys ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY tenant_keys_rls ON tenant_keys USING "
        "(organization_id = current_setting('app.org_id')::uuid);"
    )

    # CHECK constraint: residency_strict implies region must match the deployment region.
    # Enforced at app layer; we add a DB-level CHECK that residency_strict requires non-null region.
    op.execute(
        "ALTER TABLE organizations ADD CONSTRAINT organizations_residency_chk "
        "CHECK (region IS NOT NULL AND region <> '');"
    )


def downgrade() -> None:
    op.drop_table("tenant_keys")
    op.drop_constraint("organizations_residency_chk", "organizations")
    op.drop_column("organizations", "residency_strict")
    op.drop_column("organizations", "region")
