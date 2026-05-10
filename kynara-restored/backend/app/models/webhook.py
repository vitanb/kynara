"""Webhook subscriptions and the outbox of pending deliveries.

Every event-emitting code path (decision recorded, agent killed, policy
changed, audit chain broken) writes a row to ``webhook_outbox`` in the same
transaction as the underlying state change. A background worker picks them
up, signs the payload with HMAC-SHA-256 over the body, and POSTs to the
configured endpoint with retries and exponential backoff.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class WebhookEndpoint(Base, UUIDPkMixin, TimestampMixin):
    """A registered HTTPS endpoint that subscribes to one or more event types."""

    __tablename__ = "webhook_endpoints"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # The signing secret. Stored hashed (we only display once on creation).
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    secret_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    # Which events to deliver. "*" = all.
    event_types: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Delivery health
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WebhookOutbox(Base, UUIDPkMixin, TimestampMixin):
    """A queued delivery for a registered endpoint.

    The transactional outbox pattern: events are inserted with the same
    transaction that produced the state change, guaranteeing at-least-once
    delivery. The worker selects ``status='pending' AND deliver_after<=now()``,
    delivers, and updates status. Idempotency-keys make replays safe.
    """

    __tablename__ = "webhook_outbox"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum("pending", "delivered", "failed", "dead",
             name="webhook_outbox_status_enum", create_type=False),
        nullable=False, default="pending", index=True,
    )

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deliver_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(2048))
    last_response_status: Mapped[int | None] = mapped_column(Integer)

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
