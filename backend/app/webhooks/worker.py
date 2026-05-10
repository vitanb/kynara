"""Webhook delivery worker.

Run as a long-lived background task (or a separate ``arq``/``celery`` consumer
in production). The implementation here uses ``httpx`` directly so it can be
embedded for development and demos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookEndpoint, WebhookOutbox
from app.webhooks.service import sign_payload

log = logging.getLogger("kynara.webhooks")

MAX_ATTEMPTS = 8           # ~ 4 hours of backoff
DEAD_AFTER_HOURS = 24
TIMEOUT_SECONDS = 10


def _next_delay(attempt: int) -> timedelta:
    """Exponential backoff with jitter: 2**attempt seconds, max 1h."""
    base = min(60 * 60, 2**attempt)  # cap at 1 hour
    jitter = secrets.randbelow(max(1, base // 5))
    return timedelta(seconds=base + jitter)


async def deliver_one(
    client: httpx.AsyncClient,
    session: AsyncSession,
    row: WebhookOutbox,
    endpoint: WebhookEndpoint,
    *,
    secret: str,
) -> None:
    """Attempt one delivery. Updates the outbox row in-place."""
    body = json.dumps({
        "id": row.event_id,
        "type": row.event_type,
        "created": row.created_at.isoformat(),
        "data": row.payload,
    }, separators=(",", ":")).encode()

    sig = sign_payload(secret, body)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Kynara-Webhooks/1.0",
        "X-Kynara-Event": row.event_type,
        "X-Kynara-Event-ID": row.event_id,
        "X-Kynara-Signature": sig,
    }

    row.attempts += 1
    row.last_attempt_at = datetime.now(timezone.utc)
    try:
        resp = await client.post(endpoint.url, content=body, headers=headers, timeout=TIMEOUT_SECONDS)
        row.last_response_status = resp.status_code
        if 200 <= resp.status_code < 300:
            row.status = "delivered"
            row.delivered_at = datetime.now(timezone.utc)
            row.last_error = None
            endpoint.last_success_at = row.delivered_at
            endpoint.consecutive_failures = 0
            log.info("webhook.delivered", extra={"event": row.event_type, "endpoint": str(endpoint.id)})
            return
        row.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as e:
        row.last_response_status = None
        row.last_error = f"{type(e).__name__}: {e}"

    # Failure path
    endpoint.last_failure_at = datetime.now(timezone.utc)
    endpoint.consecutive_failures += 1

    if row.attempts >= MAX_ATTEMPTS:
        row.status = "dead"
        log.warning("webhook.dead", extra={"event": row.event_type, "attempts": row.attempts})
        return

    # Schedule retry
    row.deliver_after = datetime.now(timezone.utc) + _next_delay(row.attempts)
    row.status = "pending"


async def deliver_pending(
    session: AsyncSession,
    *,
    secret_lookup,        # callable: endpoint_id -> plaintext secret
    batch_size: int = 50,
) -> int:
    """Deliver up to ``batch_size`` pending rows. Returns count attempted.

    ``secret_lookup`` exists because we only store hashed secrets at rest.
    Operators should provide a KMS-backed lookup that decrypts the secret per
    delivery, or run the worker with a wrapped credential store.
    """
    now = datetime.now(timezone.utc)

    # Auto-mark very old pending rows dead
    cutoff = now - timedelta(hours=DEAD_AFTER_HOURS)
    await session.execute(
        update(WebhookOutbox)
        .where(WebhookOutbox.status == "pending", WebhookOutbox.created_at < cutoff)
        .values(status="dead")
    )

    rows = (await session.scalars(
        select(WebhookOutbox)
        .where(WebhookOutbox.status == "pending", WebhookOutbox.deliver_after <= now)
        .order_by(WebhookOutbox.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )).all()

    if not rows:
        return 0

    # Fetch all the relevant endpoints in one query
    ep_ids = list({r.endpoint_id for r in rows})
    eps = {
        e.id: e
        for e in (await session.scalars(
            select(WebhookEndpoint).where(WebhookEndpoint.id.in_(ep_ids))
        )).all()
    }

    n = 0
    async with httpx.AsyncClient() as client:
        for r in rows:
            ep = eps.get(r.endpoint_id)
            if not ep or not ep.is_enabled:
                r.status = "dead"
                r.last_error = "Endpoint missing or disabled"
                continue
            secret = await secret_lookup(ep.id)
            if not secret:
                r.status = "dead"
                r.last_error = "Signing secret unavailable"
                continue
            await deliver_one(client, session, r, ep, secret=secret)
            n += 1

    await session.commit()
    return n


async def run_loop(session_factory, secret_lookup, *, idle_seconds: float = 1.0) -> None:
    """Embed-friendly run loop. In production use a dedicated worker process."""
    while True:
        try:
            async with session_factory() as session:
                done = await deliver_pending(session, secret_lookup=secret_lookup)
            if done == 0:
                await asyncio.sleep(idle_seconds)
        except Exception:
            log.exception("webhook.worker.crash")
            await asyncio.sleep(5)
