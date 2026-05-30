"""AgentCredential model — API keys and mTLS certificates for agents."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class AgentCredential(Base, UUIDPkMixin, TimestampMixin):
    """A verifiable credential (API key or mTLS cert) issued to an agent.

    The plaintext key is returned ONCE at issuance and never stored.
    ``key_hash`` holds a SHA-256 hex digest used for lookup.
    ``key_prefix`` holds the first 8 characters for display/identification.
    """

    __tablename__ = "agent_credentials"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # "api_key" | "mtls_cert"
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # First 8 chars of the key for display (e.g. "kag_abc1")
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    # SHA-256 hex digest of the full plaintext key
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Actor string that revoked the credential, e.g. "user:<uuid>"
    revoked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
