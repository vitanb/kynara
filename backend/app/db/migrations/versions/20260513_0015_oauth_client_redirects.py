"""Widen claude-connector redirect_uris to include all Claude.ai callback paths.

The connector OAuth flow from Claude.ai uses paths like:
  https://claude.ai/api/mcp/auth_callback
  https://claude.ai/oauth/callback
  https://app.claude.ai/oauth/callback
We also allow localhost for local development testing.

Revision ID: 20260513_0015
Revises: 20260512_0014
"""
from alembic import op

revision = "20260513_0015"
down_revision = "20260512_0014"
branch_labels = None
depends_on = None

_REDIRECT_URIS = ",".join([
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.ai/oauth/callback",
    "https://app.claude.ai/oauth/callback",
    "https://app.claude.ai/api/mcp/auth_callback",
    # Local dev
    "http://localhost:5173/oauth/callback",
    "http://localhost:3000/oauth/callback",
])


def upgrade() -> None:
    op.execute(f"""
        UPDATE oauth_clients
        SET redirect_uris = '{_REDIRECT_URIS}'
        WHERE client_id = 'claude-connector'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE oauth_clients
        SET redirect_uris =
            'https://claude.ai/oauth/callback,https://app.claude.ai/oauth/callback'
        WHERE client_id = 'claude-connector'
    """)
