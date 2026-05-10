"""initial schema — orgs, users, agents, tools, policies, audit, sso, billing.

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ------------------------------------------------------------------ enums
    # Use raw SQL + DO blocks so these work correctly with SQLAlchemy 2.x async engines.
    # create_type=False tells SQLAlchemy not to re-create the type when used in op.create_table.
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE seat_role_enum AS ENUM "
        "('owner','admin','developer','auditor','member'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE agent_mode_enum AS ENUM "
        "('human_supervised','autonomous','read_only'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE policy_effect_enum AS ENUM "
        "('allow','deny','require_approval'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE sso_protocol_enum AS ENUM "
        "('oidc','saml'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))

    # Reference already-created PostgreSQL enum types by name only.
    # Using postgresql.ENUM with create_type=False avoids SQLAlchemy emitting
    # a duplicate CREATE TYPE statement during op.create_table in async context.
    seat_role    = postgresql.ENUM(name="seat_role_enum",    create_type=False)
    agent_mode   = postgresql.ENUM(name="agent_mode_enum",   create_type=False)
    effect       = postgresql.ENUM(name="policy_effect_enum", create_type=False)
    sso_protocol = postgresql.ENUM(name="sso_protocol_enum", create_type=False)

    # ------------------------------------------------------------------ orgs
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("plan", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("is_trialing", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("password_hash", sa.String(512)),
        sa.Column("external_idp", sa.String(32)),
        sa.Column("external_subject", sa.String(255)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("mfa_enrolled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_external_subject", "users", ["external_subject"])

    # --------------------------------------------------------- memberships
    op.create_table(
        "org_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat_role", seat_role, nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership"),
    )

    # ------------------------------------------------------------- sessions
    op.create_table(
        "refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("refresh_sessions.id")),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ----------------------------------------------------------------- roles
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_role_slug"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("role_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("role_id", "scope", name="uq_role_scope"),
    )

    # -------------------------------------------------------------- policies
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("effect", effect, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="500"),
        sa.Column("actions", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("resource_types", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("condition", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_policy_slug"),
    )
    op.create_table(
        "policy_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_selector", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ----------------------------------------------------------------- tools
    op.create_table(
        "tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("risk_class", sa.String(16), nullable=False, server_default="low"),
        sa.Column("input_schema", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "namespace", "name", name="uq_tool"),
    )
    op.create_table(
        "tool_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tool_id", "scope", name="uq_tool_scope"),
    )

    # ---------------------------------------------------------------- agents
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("mode", agent_mode, nullable=False, server_default="human_supervised"),
        sa.Column("model", sa.String(128)),
        sa.Column("runtime_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("daily_action_budget", sa.Integer, nullable=False, server_default="10000"),
        sa.Column("escalation_policy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("policies.id")),
        sa.Column("last_action_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_agent_slug_per_org"),
    )

    op.create_table(
        "agent_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "user_id", "organization_id", name="uq_agent_assignment"),
    )

    # -------------------------------------------------------------- api keys
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("last_four", sa.String(4), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("scopes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("rate_limit_per_minute", sa.Integer, nullable=False, server_default="600"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # -------------------------------------------------------------- sso
    op.create_table(
        "sso_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("protocol", sso_protocol, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("issuer", sa.String(512)),
        sa.Column("client_id", sa.String(255)),
        sa.Column("client_secret_enc", sa.String(2048)),
        sa.Column("idp_entity_id", sa.String(512)),
        sa.Column("idp_sso_url", sa.String(1024)),
        sa.Column("idp_x509_cert", sa.String(8192)),
        sa.Column("attribute_map", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("email_domain_allowlist", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("enforce_for_org", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_sso_slug"),
    )
    op.create_table(
        "scim_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------ billing
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(64)),
        sa.Column("stripe_subscription_id", sa.String(64)),
        sa.Column("plan", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(32), nullable=False, server_default="trialing"),
        sa.Column("seats_included", sa.Integer, nullable=False, server_default="5"),
        sa.Column("decisions_included", sa.Integer, nullable=False, server_default="100000"),
        sa.Column("overage_cents_per_1k", sa.Integer, nullable=False, server_default="50"),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("quantity", sa.BigInteger, nullable=False),
        sa.Column("dims", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_usage_org_ts", "usage_records", ["organization_id", "ts"])

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(64), nullable=False, unique=True),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("hosted_url", sa.String(1024)),
        sa.Column("pdf_url", sa.String(1024)),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ----------------------------------------------------------- audit log
    # Per-org monotonic sequence, enforced by trigger for tamper resistance.
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("on_behalf_of", sa.String(128)),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("trace_id", sa.String(64)),
        sa.Column("prev_hash", sa.String(128), nullable=False),
        sa.Column("entry_hash", sa.String(128), nullable=False),
    )
    op.create_index("ix_audit_org_seq", "audit_events", ["organization_id", "sequence"], unique=True)
    op.create_index("ix_audit_org_ts", "audit_events", ["organization_id", "ts"])
    op.create_index("ix_audit_actor", "audit_events", ["actor"])

    # ---- RLS: enforce organization_id on every tenant-scoped table ----
    # The session installs `SET LOCAL app.org_id = <uuid>`; policies check it.
    # tool_scopes and role_permissions are child tables with no organization_id column;
    # they inherit tenant isolation through their FK to tools/roles.
    for t in (
        "org_memberships", "agents", "agent_assignments", "tools",
        "roles", "policies", "policy_bindings",
        "api_keys", "sso_connections", "scim_syncs", "audit_events",
        "subscriptions", "usage_records", "invoices",
    ):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {t}_tenant_isolation ON {t}
            USING (organization_id::text = current_setting('app.org_id', true))
            WITH CHECK (organization_id::text = current_setting('app.org_id', true));
            """
        )

    # ---- audit_events: immutability + per-org monotonic sequence ----
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_no_update_delete() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_no_update_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS audit_no_update_delete();")
    for t in (
        "invoices", "usage_records", "subscriptions",
        "audit_events", "scim_syncs", "sso_connections", "api_keys",
        "agent_assignments", "agents",
        "tool_scopes", "tools",
        "policy_bindings", "policies",
        "role_permissions", "roles",
        "refresh_sessions", "org_memberships", "users", "organizations",
    ):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
    for e in ("sso_protocol_enum", "policy_effect_enum", "agent_mode_enum", "seat_role_enum"):
        op.execute(f"DROP TYPE IF EXISTS {e};")
