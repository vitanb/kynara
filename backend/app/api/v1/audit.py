"""Audit log query + chain verification + compliance report exports."""
from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import verify_chain
from app.auth.dependencies import Principal, get_principal, require_scope
from app.db.session import SessionLocal
from app.models import AuditEvent, OrgMembership, Subscription, UsageRecord

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
    principal: Principal = Depends(require_scope("audit.read")),
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
async def verify(principal: Principal = Depends(require_scope("audit.read")), session: AsyncSession = Depends(_session)):
    return await verify_chain(session, principal.org_id)


@router.get("/export")
async def export_csv(
    principal: Principal = Depends(require_scope("audit.read")),
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


@router.get("/agent-report")
async def agent_decisions_report(
    principal: Principal = Depends(require_scope("audit.read")),
    session: AsyncSession = Depends(_session),
    since: datetime | None = None,
    until: datetime | None = None,
):
    """Per-agent decision breakdown: autonomous (allow) vs human approval vs deny.

    Groups all ``policy.decision`` audit events by agent actor and outcome,
    returning counts for allow / require_approval / deny alongside totals
    and an autonomous percentage.  Useful for governance reporting.
    """
    q = (
        select(
            AuditEvent.actor,
            AuditEvent.outcome,
            func.count(AuditEvent.id).label("cnt"),
        )
        .where(
            AuditEvent.organization_id == uuid.UUID(principal.org_id),
            AuditEvent.event_type == "policy.decision",
        )
    )
    if since:
        q = q.where(AuditEvent.ts >= since)
    if until:
        q = q.where(AuditEvent.ts <= until)
    q = q.group_by(AuditEvent.actor, AuditEvent.outcome)

    rows = (await session.execute(q)).all()

    agents: dict[str, dict] = {}
    for actor, outcome, cnt in rows:
        # Only include agent actors; skip user/api_key actors
        if not (actor or "").startswith("agent:"):
            continue
        agent_id = actor.replace("agent:", "")
        if agent_id not in agents:
            agents[agent_id] = {
                "agent_id": agent_id,
                "allow": 0,
                "require_approval": 0,
                "deny": 0,
                "total": 0,
            }
        if outcome in ("allow", "require_approval", "deny"):
            agents[agent_id][outcome] += cnt
        agents[agent_id]["total"] += cnt

    result = []
    for entry in agents.values():
        total = entry["total"]
        entry["autonomous_pct"] = round(entry["allow"] / total * 100, 1) if total else 0.0
        entry["approval_pct"] = round(entry["require_approval"] / total * 100, 1) if total else 0.0
        result.append(entry)

    return sorted(result, key=lambda x: -x["total"])


# ---------------------------------------------------------------------------
# Compliance report exports
# ---------------------------------------------------------------------------

@router.get(
    "/compliance/soc2",
    summary="SOC 2 evidence pack (ZIP)",
    description=(
        "Download a ZIP archive containing the audit log CSV, chain-integrity "
        "verification result, access review, and policy decision summary — "
        "suitable as evidence for a SOC 2 Type II audit."
    ),
)
async def export_soc2_pack(
    principal: Principal = Depends(require_scope("audit.read")),
    session: AsyncSession = Depends(_session),
    since: datetime | None = None,
    until: datetime | None = None,
):
    """SOC 2 evidence pack — returns a ZIP with four artefacts."""
    now = datetime.now(tz=timezone.utc)
    since = since or (now - timedelta(days=90))
    until = until or now
    org_id = uuid.UUID(principal.org_id)

    # 1. Full audit log CSV
    audit_rows = (await session.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == org_id,
               AuditEvent.ts >= since, AuditEvent.ts <= until)
        .order_by(AuditEvent.sequence.asc())
    )).all()
    audit_buf = io.StringIO()
    w = csv.writer(audit_buf)
    w.writerow(["sequence", "ts", "event_type", "actor", "resource_type",
                "resource_id", "outcome", "ip_address", "entry_hash", "prev_hash"])
    for r in audit_rows:
        w.writerow([r.sequence, r.ts.isoformat(), r.event_type, r.actor,
                    r.resource_type or "", r.resource_id or "", r.outcome,
                    str(r.ip_address) if r.ip_address else "", r.entry_hash, r.prev_hash])

    # 2. Chain integrity verification
    chain_result = await verify_chain(session, principal.org_id)

    # 3. Access review — current org members and roles
    members = (await session.scalars(
        select(OrgMembership).where(OrgMembership.organization_id == org_id)
    )).all()
    access_buf = io.StringIO()
    aw = csv.writer(access_buf)
    aw.writerow(["user_id", "role", "status", "joined_at"])
    for m in members:
        aw.writerow([str(m.user_id), m.role, m.status,
                     m.created_at.isoformat() if hasattr(m, "created_at") and m.created_at else ""])

    # 4. Policy decision summary
    decision_rows = (await session.execute(
        select(AuditEvent.outcome, func.count(AuditEvent.id).label("cnt"))
        .where(AuditEvent.organization_id == org_id,
               AuditEvent.event_type == "policy.decision",
               AuditEvent.ts >= since, AuditEvent.ts <= until)
        .group_by(AuditEvent.outcome)
    )).all()
    summary = {row.outcome: row.cnt for row in decision_rows}
    summary_text = json.dumps({
        "period_start": since.isoformat(),
        "period_end": until.isoformat(),
        "org_id": principal.org_id,
        "decisions": summary,
        "chain_integrity": chain_result,
        "generated_at": now.isoformat(),
    }, indent=2)

    # Pack into ZIP
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("audit_log.csv", audit_buf.getvalue())
        zf.writestr("chain_integrity.json", json.dumps(chain_result, indent=2))
        zf.writestr("access_review.csv", access_buf.getvalue())
        zf.writestr("decision_summary.json", summary_text)
    zip_buf.seek(0)

    filename = f"soc2-evidence-{since.strftime('%Y%m%d')}-{until.strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/compliance/hipaa",
    summary="HIPAA access report (CSV)",
    description=(
        "Download a CSV of all access events (who accessed what resource and when) "
        "in the requested period. Required for HIPAA audit controls §164.312(b)."
    ),
)
async def export_hipaa_access_report(
    principal: Principal = Depends(require_scope("audit.read")),
    session: AsyncSession = Depends(_session),
    since: datetime | None = None,
    until: datetime | None = None,
):
    now = datetime.now(tz=timezone.utc)
    since = since or (now - timedelta(days=365))
    until = until or now
    org_id = uuid.UUID(principal.org_id)

    rows = (await session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == org_id,
            AuditEvent.ts >= since,
            AuditEvent.ts <= until,
            AuditEvent.event_type.in_([
                "policy.decision", "data.read", "data.write",
                "auth.login", "auth.logout", "user.impersonated",
            ]),
        )
        .order_by(AuditEvent.ts.asc())
        .limit(50_000)
    )).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "actor", "action", "resource_type", "resource_id",
                "outcome", "ip_address", "request_id"])
    for r in rows:
        w.writerow([
            r.ts.isoformat(), r.actor, r.event_type,
            r.resource_type or "", r.resource_id or "",
            r.outcome, str(r.ip_address) if r.ip_address else "",
            r.request_id or "",
        ])

    buf.seek(0)
    filename = f"hipaa-access-{since.strftime('%Y%m%d')}-{until.strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/compliance/access-review",
    summary="Quarterly access review (CSV)",
    description=(
        "Current org members with roles, last-login timestamps, and active JIT grants. "
        "Designed to be sent to org owners for quarterly review."
    ),
)
async def export_access_review(
    principal: Principal = Depends(require_scope("audit.read")),
    session: AsyncSession = Depends(_session),
):
    org_id = uuid.UUID(principal.org_id)

    # Members with roles
    members = (await session.scalars(
        select(OrgMembership).where(OrgMembership.organization_id == org_id)
    )).all()

    # Last login per user (last auth.login audit event)
    last_logins_rows = (await session.execute(
        select(AuditEvent.actor, func.max(AuditEvent.ts).label("last_login"))
        .where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "auth.login",
        )
        .group_by(AuditEvent.actor)
    )).all()
    last_login_map = {
        row.actor.replace("user:", ""): row.last_login
        for row in last_logins_rows
        if (row.actor or "").startswith("user:")
    }

    # Active JIT grants
    try:
        from app.models.jit_grant import JitGrant
        now = datetime.now(tz=timezone.utc)
        jit_rows = (await session.scalars(
            select(JitGrant).where(
                JitGrant.organization_id == org_id,
                JitGrant.is_active.is_(True),
                JitGrant.expires_at > now,
            )
        )).all()
        jit_map: dict[str, list] = {}
        for g in jit_rows:
            uid = str(g.user_id)
            jit_map.setdefault(uid, []).append(
                f"{','.join(g.scopes)} until {g.expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )
    except Exception:
        jit_map = {}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "role", "status", "member_since", "last_login", "active_jit_grants"])
    for m in members:
        uid = str(m.user_id)
        last_login = last_login_map.get(uid)
        w.writerow([
            uid, m.role, m.status,
            m.created_at.isoformat() if hasattr(m, "created_at") and m.created_at else "",
            last_login.isoformat() if last_login else "never",
            "; ".join(jit_map.get(uid, [])) or "none",
        ])

    buf.seek(0)
    today = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    filename = f"access-review-{today}.csv"
    return StreamingResponse(
        iter([buf.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
 total * 100, 1) if total else 0.0
        result.append(entry)

    return sorted(result, key=lambda x: -x["total"])
