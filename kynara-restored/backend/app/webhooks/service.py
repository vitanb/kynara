"""Webhook service: enqueue events into the outbox, register/rotate endpoints."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookEndpoint, WebhookOutbox

# Event vocabulary — keep in sync with docs/api/integration-guide.md.
EVENT_TYPES = (
    "decision.allowed",
    "decision.denied",
    "decision.approval_requested",
    "decision.approved",
    "decision.rejected",
    "agent.created",
    "agent.killed",
    "agent.permissions_changed",
    "policy.changed",
    "audit.chain_broken",
    "approval.expired",
)


def hash_secret(secret: str) -> str:
    """Hash a webhook secret for at-rest storage."""
    return hashlib.sha256(("kynara-webhook-pepper:" + secret).encode()).hexdigest()


def sign_payload(secret: str, body: bytes) -> str:
    """Compute X-Kynara-Signature value: 'sha256=<hex hmac>'."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256=v1,{digest}"


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


class WebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_endpoint(
        self,
        org_id: str,
        url: str,
        event_types: Iterable[str],
        description: str | None = None,
    ) -> tuple[WebhookEndpoint, str]:
        """Create an endpoint, returning (record, plaintext_secret).

        The secret is shown to the user exactly once.
        """
        # Validate event types
        accepted = set(EVENT_TYPES) | {"*"}
        for et in event_types:
            if et not in accepted:
                raise ValueError(f"Unknown event type: {et}")

        secret = "whsec_" + secrets.token_urlsafe(32)
        endpoint = WebhookEndpoint(
            organization_id=uuid.UUID(org_id),
            url=url,
            description=description,
            secret_hash=hash_secret(secret),
            secret_prefix=secret[:12],
            event_types=list(event_types),
        )
        self.session.add(endpoint)
        await self.session.flush()
        return endpoint, secret

    async def rotate_secret(self, endpoint: WebhookEndpoint) -> str:
        secret = "whsec_" + secrets.token_urlsafe(32)
        endpoint.secret_hash = hash_secret(secret)
        endpoint.secret_prefix = secret[:12]
        await self.session.flush()
        return secret

    async def enqueue(
        self,
        org_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Insert outbox rows for every endpoint subscribed to ``event_type``.

        Called from inside the same transaction as the underlying state change.
        Returns count of rows enqueued.
        """
        if event_type not in EVENT_TYPES:
            # We tolerate unknown types — log them but don't reject; otherwise a
            # forgotten registration here would silently drop business events.
            pass

        eps = (await self.session.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == uuid.UUID(org_id),
                WebhookEndpoint.is_enabled.is_(True),
            )
        )).all()

        n = 0
        for ep in eps:
            if "*" not in ep.event_types and event_type not in ep.event_types:
                continue
            row = WebhookOutbox(
                organization_id=uuid.UUID(org_id),
                endpoint_id=ep.id,
                event_type=event_type,
                event_id="evt_" + secrets.token_urlsafe(16),
                payload=payload,
            )
            self.session.add(row)
            n += 1
        return n


async def emit(session: AsyncSession, org_id: str, event_type: str, payload: dict) -> int:
    """Convenience: enqueue an event for all matching endpoints in this org."""
    svc = WebhookService(session)
    return await svc.enqueue(org_id=org_id, event_t