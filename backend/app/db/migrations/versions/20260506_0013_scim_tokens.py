"""scim_tokens table — per-org bearer tokens for SCIM 2.0 authentication.

The previous ScimSync model only tracked provisioning events (external_id,
resource_type, last_sync_at, payload) and never stored token credentials.
This migration adds a dedicated scim_tokens table so SCIM authentication
works correctly.

Revision ID: 0013_scim_tokens
Revises: 0012_superadmin
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0013_scim_tokens"
down_revision = "0012_superadmin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scim_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # HMAC-SHA256(token, jwt_secret) — 64 hex chars
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(255), nullable=False, server_default="Default"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_scim_tokens_token_hash", "scim_tokens", ["token_hash"], unique=True)
    op.create_index("ix_scim_tokens_org_id", "scim_tokens", ["organization_id"])

    # Enable Row-Level Security so tenants only see their own tokens
    op.execute("ALTER TABLE scim_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY scim_tokens_org_isolation ON scim_tokens
        USING (organization_id::text = current_setting('app.org_id', true))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS scim_tokens_org_isolation ON scim_tokens")
    op.drop_table("scim_tokens")
