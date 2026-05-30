"""GitConnection model — stores per-org git repo registrations for policy-as-code sync."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class GitConnection(Base, UUIDPkMixin, TimestampMixin):
    """Links an org to a git repository that holds their policy bundle."""

    __tablename__ = "git_connections"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "github" | "gitlab"
    provider: Mapped[str] = mapped_column(String(32), nullable=False)

    # e.g. https://github.com/acme/kynara-policies
    repo_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")

    # Encrypted token bundle from kms.encrypt_for_tenant()
    access_token_enc: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # HMAC secret used to verify incoming push webhooks
    webhook_secret: Mapped[str] = mapped_column(String(128), nullable=False)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Commit SHA of last successfully applied sync
    last_sync_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # "idle" | "syncing" | "error"
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")

    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
