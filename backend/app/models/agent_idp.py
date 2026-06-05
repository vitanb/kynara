"""SQLAlchemy model for agent identity provider sync (e.g. Okta).

An ``AgentIdentityProvider`` connects an external IdP (Okta first) and imports
its AI-agent identities into Kynara as ``Agent`` records, keeping them in sync
and optionally mapping IdP groups to Kynara roles.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class AgentIdentityProvider(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "agent_identity_providers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="okta")
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Okta org URL, e.g. https://acme.okta.com
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # SSWS API token (or OAuth token), encrypted at rest.
    api_token_enc: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    # "agents" → Okta first-class agent identities (GET /api/v1/agents)
    # "group"  → members of a designated Okta group represent agents
    sync_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="agents")
    group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Mode assigned to newly imported agents.
    default_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="human_supervised")

    # { "<okta group name>": "<kynara role slug>" } — first match wins per agent.
    role_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # User that role-mapped, synced agents act on behalf of (required for role grants).
    default_on_behalf_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # When true, Okta-sourced agents not seen in the latest sync are deactivated.
    deactivate_missing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_synced_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_sync_stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
