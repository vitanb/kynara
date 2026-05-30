"""Real-time agent activity stream via Server-Sent Events.

Endpoints:
  GET /activity/stream  — SSE feed of live policy decisions for the org
  GET /activity/summary — current-period aggregate stats (non-streaming)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, require_scope
from app.db.session import SessionLocal
from app.models import AuditEvent

router = APIRouter(prefix="/activity", tags=["activity"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------

async def _event_generator(org_id: str):
    """Poll for new policy.decision events and yield them as SSE."""
    last_sequence: int = 0
    heartbeat_counter = 0

    # Seed the cursor at the current max sequence so we only stream NEW events
    async with SessionLocal() as session:
        max_seq = await session.scalar(
            select(func.max(AuditEvent.sequence)).where(
                AuditEvent.organization_id == uuid.UUID(org_id),
            )
        )
        last_sequence = int(max_seq or 0)

    while True:
        try:
            async with SessionLocal() as session:
                rows = (await session.scalars(
                    select(AuditEvent)
                    .where(
                        AuditEvent.organization_id == uuid.UUID(org_id),
                        AuditEvent.event_type == "policy.decision",
                        AuditEvent.sequence > last_sequence,
                    )
                    .order_by(AuditEvent.sequence.asc())
                    .limit(50)
                )).all()

            for row in rows:
                last_sequence = row.sequence
                actor = row.actor or ""
                agent_id = actor.replace("agent:", "") if actor.startswith("agent:") else None
                payload = {
                    "sequence": row.sequence,
                    "ts": row.ts.isoformat(),
                    "actor": actor,
                    "agent_id": agent_id,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "effect": row.outcome,
                    "event_type": row.event_type,
                }
                yield f"event: decision\ndata: {json.dumps(payload)}\n\n"

            # Heartbeat every ~15 seconds (poll is 2s × 7 iterations = 14s)
            heartbeat_counter += 1
            if heartbeat_counter >= 7:
                heartbeat_counter = 0
                yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now(tz=timezone.utc).isoformat()})}\n\n"

        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

        await asyncio.sleep(2)


@router.get("/stream", summary="Live SSE feed of policy decisions")
async def activity_stream(
    principal: Principal = Depends(require_scope("audit.read")),
):
    """Stream policy decision events for the org as Server-Sent Events.

    Connect with:
        const es = new EventSource('/activity/stream', { withCredentials: true });
        es.addEventListener('decision', e => console.log(JSON.parse(e.data)));
        es.addEventListener('heartbeat', e => console.log('ping'));
    """
    return StreamingResponse(
        _event_generator(principal.org_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Summary stats (non-streaming)
# ---------------------------------------------------------------------------

@router.get("/summary", summary="Current-period agent activity summary")
async def activity_summary(
    principal: Principal = Depends(require_scope("audit.read")),
    session: AsyncSession = Depends(_session),
):
    """Return aggregate decision stats for the last hour and last minute."""
    now = datetime.now(tz=timezone.utc)
    one_min_ago = now - timedelta(minutes=1)
    one_hour_ago = now - timedelta(hours=1)
    five_min_ago = now - timedelta(minutes=5)
    org_id = uuid.UUID(principal.org_id)

    # Decisions in the last hour grouped by outcome
    hour_rows = (await session.execute(
        select(AuditEvent.outcome, func.count(AuditEvent.id).label("cnt"))
        .where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "policy.decision",
            AuditEvent.ts >= one_hour_ago,
        )
        .group_by(AuditEvent.outcome)
    )).all()
    hour_totals = {r.outcome: r.cnt for r in hour_rows}
    decisions_last_hour = sum(hour_totals.values())

    # Decisions in the last minute
    decisions_last_minute = int(await session.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "policy.decision",
            AuditEvent.ts >= one_min_ago,
        )
    ) or 0)

    # Active agents (any decision in last 5 min)
    active_agents = (await session.execute(
        select(func.count(func.distinct(AuditEvent.actor))).where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "policy.decision",
            AuditEvent.actor.like("agent:%"),
            AuditEvent.ts >= five_min_ago,
        )
    )).scalar() or 0

    def rate(outcome: str) -> float:
        if not decisions_last_hour:
            return 0.0
        return round(hour_totals.get(outcome, 0) / decisions_last_hour * 100, 1)

    return {
        "as_of": now.isoformat(),
        "active_agents_last_5min": int(active_agents),
        "decisions_last_minute": decisions_last_minute,
        "decisions_last_hour": decisions_last_hour,
        "allow_rate_pct": rate("allow"),
        "deny_rate_pct": rate("deny"),
        "approval_rate_pct": rate("require_approval"),
    }
