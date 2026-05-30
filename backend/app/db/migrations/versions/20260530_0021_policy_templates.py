"""policy_templates table + 5 starter templates

Revision ID: 20260530_0021
Revises: 20260530_0020
Create Date: 2026-05-30
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260530_0021"
down_revision = "20260530_0020"
branch_labels = None
depends_on = None

# Helper to produce a deterministic UUID from a slug so re-runs are idempotent
def _slug_uuid(slug: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kynara.policy_template.{slug}"))


STARTER_TEMPLATES = [
    {
        "id": _slug_uuid("crm-agent-safe"),
        "slug": "crm-agent-safe",
        "display_name": "CRM Agent — Safe Defaults",
        "description": "Allows reading CRM contacts freely; requires human approval before any CRM write operation.",
        "category": "crm",
        "author": "kynara",
        "tags": "{crm,contacts,read-only-writes}",
        "template_data": """{
            "policies": [
                {
                    "slug": "crm-read-allow",
                    "display_name": "Allow CRM reads",
                    "effect": "allow",
                    "priority": 400,
                    "actions": ["crm:contacts.read", "crm:accounts.read"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "crm-write-approval",
                    "display_name": "Require approval for CRM writes",
                    "effect": "require_approval",
                    "priority": 300,
                    "actions": ["crm:contacts.write", "crm:accounts.write", "crm:*.create", "crm:*.update", "crm:*.delete"],
                    "resource_types": [],
                    "condition": {}
                }
            ]
        }""",
    },
    {
        "id": _slug_uuid("code-agent-restricted"),
        "slug": "code-agent-restricted",
        "display_name": "Code Agent — Restricted",
        "description": "Allows file reads, blocks file deletions, and requires approval before any file write.",
        "category": "code",
        "author": "kynara",
        "tags": "{code,files,restricted}",
        "template_data": """{
            "policies": [
                {
                    "slug": "code-file-read-allow",
                    "display_name": "Allow file reads",
                    "effect": "allow",
                    "priority": 400,
                    "actions": ["file:read", "file:list"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "code-file-delete-deny",
                    "display_name": "Deny file deletions",
                    "effect": "deny",
                    "priority": 200,
                    "actions": ["file:delete"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "code-file-write-approval",
                    "display_name": "Require approval for file writes",
                    "effect": "require_approval",
                    "priority": 300,
                    "actions": ["file:write", "file:create", "file:overwrite"],
                    "resource_types": [],
                    "condition": {}
                }
            ]
        }""",
    },
    {
        "id": _slug_uuid("data-analyst-agent"),
        "slug": "data-analyst-agent",
        "display_name": "Data Analyst Agent",
        "description": "Allows database queries freely, requires approval for writes, and permanently blocks DROP operations.",
        "category": "data",
        "author": "kynara",
        "tags": "{data,database,analytics}",
        "template_data": """{
            "policies": [
                {
                    "slug": "data-query-allow",
                    "display_name": "Allow database queries",
                    "effect": "allow",
                    "priority": 400,
                    "actions": ["database:query", "database:read", "database:select"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "data-drop-deny",
                    "display_name": "Deny database DROP",
                    "effect": "deny",
                    "priority": 100,
                    "actions": ["database:drop", "database:truncate"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "data-write-approval",
                    "display_name": "Require approval for database writes",
                    "effect": "require_approval",
                    "priority": 300,
                    "actions": ["database:write", "database:insert", "database:update", "database:delete"],
                    "resource_types": [],
                    "condition": {}
                }
            ]
        }""",
    },
    {
        "id": _slug_uuid("email-agent"),
        "slug": "email-agent",
        "display_name": "Email Agent",
        "description": "Allows reading emails, requires approval before sending, and blocks bulk delete operations.",
        "category": "email",
        "author": "kynara",
        "tags": "{email,communication}",
        "template_data": """{
            "policies": [
                {
                    "slug": "email-read-allow",
                    "display_name": "Allow email reads",
                    "effect": "allow",
                    "priority": 400,
                    "actions": ["email:read", "email:list", "email:search"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "email-delete-all-deny",
                    "display_name": "Deny bulk email deletion",
                    "effect": "deny",
                    "priority": 100,
                    "actions": ["email:delete_all", "email:bulk_delete"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "email-send-approval",
                    "display_name": "Require approval for sending email",
                    "effect": "require_approval",
                    "priority": 300,
                    "actions": ["email:send", "email:reply", "email:forward"],
                    "resource_types": [],
                    "condition": {}
                }
            ]
        }""",
    },
    {
        "id": _slug_uuid("read-only-agent"),
        "slug": "read-only-agent",
        "display_name": "Read-Only Agent",
        "description": "Permits any read action (matching *:read pattern) and denies all write operations by default.",
        "category": "general",
        "author": "kynara",
        "tags": "{read-only,safe,general}",
        "template_data": """{
            "policies": [
                {
                    "slug": "read-all-allow",
                    "display_name": "Allow all reads",
                    "effect": "allow",
                    "priority": 400,
                    "actions": ["*:read", "*:list", "*:get", "*:search"],
                    "resource_types": [],
                    "condition": {}
                },
                {
                    "slug": "write-all-deny",
                    "display_name": "Deny all writes",
                    "effect": "deny",
                    "priority": 300,
                    "actions": ["*:write", "*:create", "*:update", "*:delete", "*:modify"],
                    "resource_types": [],
                    "condition": {}
                }
            ]
        }""",
    },
]


def upgrade() -> None:
    op.create_table(
        "policy_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("author", sa.String(128), nullable=False, server_default="kynara"),
        sa.Column("template_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("install_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_policy_templates_category", "policy_templates", ["category"])

    # Insert the 5 starter templates.
    # Use CAST() instead of :: so SQLAlchemy's text() parser does not mistake
    # the colon in ::jsonb / ::text[] for a named bind-parameter prefix.
    for t in STARTER_TEMPLATES:
        op.execute(
            sa.text(
                """
                INSERT INTO policy_templates
                    (id, slug, display_name, description, category, author,
                     template_data, tags, install_count, is_published, created_at, updated_at)
                VALUES
                    (:id, :slug, :display_name, :description, :category, :author,
                     CAST(:template_data AS jsonb), CAST(:tags AS text[]), 0, true, now(), now())
                ON CONFLICT (slug) DO NOTHING
                """
            ).bindparams(
                id=t["id"],
                slug=t["slug"],
                display_name=t["display_name"],
                description=t["description"],
                category=t["category"],
                author=t["author"],
                template_data=t["template_data"],
                tags=t["tags"],
            )
        )


def downgrade() -> None:
    op.drop_index("ix_policy_templates_category", table_name="policy_templates")
    op.drop_table("policy_templates")
