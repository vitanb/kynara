"""Audit log query + chain verification."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import verify_chain
from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])


async def _session():
    async with SessionLocal() as s:
        yield s


class AuditEventOut(BaseModel):
    id: str
    sequence: int
    ts: datetime
    event_type: str
    actor: str
    on_behalf_of: str | None
    resource_type: str | None
    resource_id: str | None
    outcome: str
    payload: dict
    ip_address: str | None
    request_id: str | None
    prev_hash: str
    entry_hash: str


@router.get("/events", response_model=list[AuditEventOut])
async def list_events(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
    actor: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    outcome: str | None = None,
    cursor: int | None = Query(default=None, description="return events with sequence < cursor (newest-first paging)"),
    since_sequence: int | None = Query(default=None, description="return events with sequence > this value (polling cursor, oldest-first)"),
    limit: int = Query(default=50, le=500),
):
    q = select(AuditEvent).where(AuditEvent.organization_id == uuid.UUID(principal.org_id))
    if actor: q = q.where(AuditEvent.actor == actor)
    if event_type: q = q.where(AuditEvent.event_type == event_type)
    if outcome: q = q.where(AuditEvent.outcome == outcome)
    if since: q = q.where(AuditEvent.ts >= since)
    if until: q = q.where(AuditEvent.ts <= until)
    if cursor is not None: q = q.where(AuditEvent.sequence < cursor)
    if since_sequence is not None:
        # Polling mode: return events NEWER than the watermark, oldest-first
        q = q.where(AuditEvent.sequence > since_sequence).order_by(AuditEvent.sequence.asc())
    else:
        q = q.order_by(AuditEvent.sequence.desc())
    q = q.limit(limit)
    rows = (await session.scalars(q)).all()
    return [AuditEventOut(
        id=str(r.id), sequence=r.sequence, ts=r.ts, event_type=r.event_type,
        actor=r.actor, on_behalf_of=r.on_behalf_of,
        resource_type=r.resource_type, resource_id=r.resource_id,
        outcome=r.outcome, payload=r.payload,
        ip_address=str(r.ip_address) if r.ip_address else None,
        request_id=r.request_id,
        prev_hash=r.prev_hash, entry_hash=r.entry_hash,
    ) for r in rows]


@router.post("/verify")
async def verify(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(_session)):
    return await verify_chain(session, principal.org_id)


@router.get("/export")
async def export_csv(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
    actor: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    outcome: str | None = None,
    limit: int = Query(default=5000, le=10000),
):
    """Export audit events as a CSV file (up to 10 000 rows)."""
    q = select(AuditEvent).where(AuditEvent.organization_id == uuid.UUID(principal.org_id))
    if actor:      q = q.where(AuditEvent.actor == actor)
    if event_type: q = q.where(AuditEvent.event_type == event_type)
    if outcome:    q = q.where(AuditEvent.outcome == outcome)
    if since:      q = q.where(AuditEvent.ts >= since)
    if until:      q = q.where(AuditEvent.ts <= until)
    q = q.order_by(AuditEvent.sequence.desc()).limit(limit)
    rows = (await session.scalars(q)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "sequence", "ts", "event_type", "actor", "on_behalf_of",
        "resource_type", "resource_id", "outcome", "ip_address",
        "request_id", "entry_hash",
    ])
    for r in rows:
        writer.writerow([
            r.sequence, r.ts.isoformat(), r.event_type, r.actor, r.on_behalf_of or "",
            r.resource_type or "", r.resource_id or "", r.outcome,
            str(r.ip_address) if r.ip_address else "",
            r.request_id or "", r.entry_hash,
        ])

    buf.seek(0)
    filename = f"audit-export-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
