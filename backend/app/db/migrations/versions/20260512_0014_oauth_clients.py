"""oauth_clients and oauth_codes tables for MCP connector OAuth 2.0 flow.

Supports Authorization Code + PKCE (S256).  No client_secret for public clients
(Claude is a public client).  Access tokens reuse the existing JWT infrastructure.

Revision ID: 20260512_0014
Revises: 20260506_0013
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260512_0014"
down_revision = "20260506_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── oauth_clients ────────────────────────────────────────────────────────
    op.create_table(
        "oauth_clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False, unique=True),
        sa.Column("client_name", sa.String(255), nullable=False),
        # Comma-separated allowed redirect URIs
        sa.Column("redirect_uris", sa.Text, nullable=False),
        # Comma-separated allowed scopes
        sa.Column("allowed_scopes", sa.Text, nullable=False,
                  server_default="read"),
        sa.Column("is_public", sa.Boolean, nullable=False,
                  server_default="true"),   # public = no client_secret
        sa.Column("client_secret_hash", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_oauth_clients_client_id", "oauth_clients", ["client_id"], unique=True)

    # ── oauth_codes ──────────────────────────────────────────────────────────
    # Short-lived authorization codes (TTL enforced in app, not DB)
    op.create_table(
        "oauth_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(128), nullable=False, unique=True),
        sa.Column("client_id", sa.String(128),
                  sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("redirect_uri", sa.Text, nullable=False),
        sa.Column("scope", sa.Text, nullable=False),
        # PKCE
        sa.Column("code_challenge", sa.String(128), nullable=True),
        sa.Column("code_challenge_method", sa.String(10), nullable=True),
        sa.Column("used", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_oauth_codes_code", "oauth_codes", ["code"], unique=True)

    # Seed the Anthropic / Claude connector client
    op.execute("""
        INSERT INTO oauth_clients
            (client_id, client_name, redirect_uris, allowed_scopes, is_public)
        VALUES
            ('claude-connector',
             'Claude (Anthropic)',
             'https://claude.ai/oauth/callback,https://app.claude.ai/oauth/callback',
             'read write',
             true)
    """)


def downgrade() -> None:
    op.drop_table("oauth_codes")
    op.drop_table("oauth_clients")
