"""Per-org chat integration configuration.

Each organization configures its own Slack and/or Teams settings.
Sensitive values (tokens, secrets) are stored encrypted using the
server-side ENCRYPTION_KEY — never in plaintext.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class OrgIntegration(Base, UUIDPkMixin, TimestampMixin):
    """One row per org — upserted when admin saves integration settings."""

    __tablename__ = "org_integrations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )

    # ── Slack ──────────────────────────────────────────────────────────────
    # Option A: Bot token (preferred — allows updating existing messages)
    slack_bot_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_signing_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Option B: Incoming Webhook URL (simpler — no interactive buttons)
    slack_webhook_url_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    slack_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Microsoft Teams ────────────────────────────────────────────────────
    teams_webhook_url_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    teams_callback_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    teams_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── PagerDuty ──────────────────────────────────────────────────────────────
    pagerduty_routing_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagerduty_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Email notifications ────────────────────────────────────────────────────
    # Comma-separated list of email addresses for approval notifications
    approval_email_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
