"""Hash-chained audit log.

Each org maintains an append-only chain. The ``entry_hash`` of event N is

    sha256(prev_hash || canonical_json(payload_N))

and subsequent events store that as their ``prev_hash``. Any retroactive mutation of a
past event cascades and breaks the chain — visible to the integrity verification job.

A daily "anchor" publishes the current tip hash to Postgres plus optionally an external
WORM store (S3 with Object Lock, or a blockchain notary). Auditors can independently
re-compute the chain at any point in time.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telemetry import audit_writes_total
from app.models import AuditEvent
from app.policy.engine import Decision

_GENESIS = "0" * 64  # hash seed for the first event in a chain


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


async def _next_sequence_and_prev_hash(session: AsyncSession, org_id: str) -> tuple[int, str]:
    row = (
        await session.execute(
            select(AuditEvent.sequence, AuditEvent.entry_hash)
            .where(AuditEvent.organization_id == uuid.UUID(org_id))
            .order_by(AuditEvent.sequence.desc())
            .limit(1)
        )
    ).first()
    if not row:
        return 1, _GENESIS
    return row.sequence + 1, row.entry_hash


async def _append(
    session: AsyncSession,
    *,
    org_id: str,
    event_type: str,
    actor: str,
    on_behalf_of: str | None,
    resource_type: str | None,
    resource_id: str | None,
    outcome: str,
    payload: dict[str, Any],
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None = None,
    trace_id: str | None = None,
) -> AuditEvent:
    seq, prev = await _next_sequence_and_prev_hash(session, org_id)
    ts = datetime.now(tz=timezone.utc)
    body = {
        "sequence": seq,
        "ts": ts.isoformat(),
        "event_type": event_type,
        "actor": actor,
        "on_behalf_of": on_behalf_of,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "payload": payload,
        "request_id": request_id,
        "ip_address": ip_address,
    }
    entry_hash = hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()

    ev = AuditEvent(
        organization_id=uuid.UUID(org_id),
        sequence=seq,
        ts=ts,
        event_type=event_type,
        actor=actor,
        on_behalf_of=on_behalf_of,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        payload=payload,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        trace_id=trace_id,
        prev_hash=prev,
        entry_hash=entry_hash,
    )
    session.add(ev)
    await session.flush()
    await session.commit()
    audit_writes_total.inc()
    return ev


async def record_decision(
    session: AsyncSession,
    *,
    org_id: str,
    actor: str,
    on_behalf_of: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    decision: Decision,
    request_id: str | None,
    ip_address: str | None,
) -> AuditEvent:
    return await _append(
        session,
        org_id=org_id,
        event_type="policy.decision",
        actor=actor,
        on_behalf_of=on_behalf_of,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=decision.effect,
        payload={"action": action, **decision.to_audit_payload()},
        request_id=request_id,
        ip_address=ip_address,
    )


async def record_auth(
    session: AsyncSession,
    *,
    org_id: str,
    actor: str,
    event: str,        # "login.success" | "login.failure" | "sso.login" | "logout" | ...
    outcome: str,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    return await _append(
        session,
        org_id=org_id,
        event_type=f"auth.{event}",
        actor=actor,
        on_behalf_of=None,
        resource_type=None,
        resource_id=None,
        outcome=outcome,
        payload=payload or {},
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def record_admin(
    session: AsyncSession,
    *,
    org_id: str,
    actor: str,
    event_type: str,
    resource_type: str,
    resource_id: str,
    payload: dict[str, Any],
    outcome: str = "allow",
    request_id: str | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    return await _append(
        session,
        org_id=org_id,
        event_type=event_type,
        actor=actor,
        on_behalf_of=None,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        payload=payload,
        request_id=request_id,
        ip_address=ip_address,
    )


# ------------------------------------------------------------- verification --
async def verify_chain(session: AsyncSession, org_id: str, since_sequence: int = 0) -> dict:
    """Walks the chain forward and confirms every entry_hash is correct.

    Returns { ok: bool, broken_at: int | None, tip: str, count: int }.
    """
    rows = (
        await session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.organization_id == uuid.UUID(org_id),
                AuditEvent.sequence > since_sequence,
            )
            .order_by(AuditEvent.sequence.asc())
        )
    ).scalars().all()

    prev = _GENESIS if since_sequence == 0 else (
        await session.scalar(
            select(AuditEvent.entry_hash).where(
                AuditEvent.organization_id == uuid.UUID(org_id),
                AuditEvent.sequence == since_sequence,
            )
        )
    ) or _GENESIS

    for ev in rows:
        body = {
            "sequence": ev.sequence,
            "ts": ev.ts.isoformat(),
            "event_type": ev.event_type,
            "actor": ev.actor,
            "on_behalf_of": ev.on_behalf_of,
            "resource_type": ev.resource_type,
            "resource_id": ev.resource_id,
            "outcome": ev.outcome,
            "payload": ev.payload,
            "request_id": ev.request_id,
            "ip_address": ev.ip_address,
        }
        expected = hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()
        if expected != ev.entry_hash or ev.prev_hash != prev:
            return {"ok": False, "broken_at": ev.sequence, "tip": prev, "count": len(rows)}
        prev = ev.entry_hash

    return {"ok": True, "broken_at": None, "tip": prev, "count": len(rows)}
