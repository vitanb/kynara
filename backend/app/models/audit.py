from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPkMixin


class AuditEvent(Base, UUIDPkMixin):
    """Hash-chained audit event.

    ``prev_hash`` is the ``entry_hash`` of the previous event in this org's chain. A daily
    anchor job publishes the tip hash to Postgres plus (optionally) an external WORM store
    so any retroactive edits become detectable.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_org_seq", "organization_id", "sequence"),
        Index("ix_audit_org_ts", "organization_id", "ts"),
        Index("ix_audit_actor", "actor"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Monotonic per-org sequence (assigned by DB trigger; see migration)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # What happened
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Dot-namespace ("policy.decision", "auth.login", "agent.tool.call", ...)

    # Who did it — "user:<uuid>" | "agent:<uuid>" | "system" | "api_key:<uuid>"
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    # Who they acted on behalf of, if delegation
    on_behalf_of: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Target of the action
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Outcome: "allow" | "deny" | "error" | "info"
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)

    # Full structured payload (sanitized of PII via redaction service before insert)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Merkle-chain fields
    prev_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(128), nullable=False)
