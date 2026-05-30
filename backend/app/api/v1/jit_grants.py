"""Just-in-Time (JIT) grant endpoints.

A JIT grant is a time-bound elevation of a user's effective scopes. Used for
break-glass scenarios: "give me ``crm:write`` for 2 hours to debug a prod
escalation." Every grant carries a justification and a link to the originating
ticket. Every grant create/revoke is recorded in the audit chain.

Self-service flow (Task #14)
-----------------------------
Any authenticated user can POST /jit-grants/request to ask for a temporary
elevation.  This creates an ApprovalRequest with request_type="jit_elevation"
and returns the approval ID so the requester can poll status.

When an admin approves that request via POST /approvals/{id}/approve the hook
``auto_fulfill_jit_elevation`` (called from approvals.py) automatically creates
the JitGrant with the requested scopes and duration.

Users can view their own pending/recent requests via GET /jit-grants/my-requests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import ApprovalRequest
from app.models.jit_grant import JitGrant
from app.webhooks.service import emit

router = APIRouter(prefix="/jit-grants", tags=["jit"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _admin(p: Principal):
    if p.seat_role not in ("owner", "admin"):
        raise HTTPException(403, "Requires owner or admin role")


class GrantIn(BaseModel):
    user_id: str
    scopes: list[str]
    duration_minutes: int = Field(60, ge=5, le=480)
    justification: str = Field(..., min_length=10, max_length=2048)
    ticket_url: str | None = None


class GrantOut(BaseModel):
    id: str
    user_id: str
    granted_by_user_id: str
    scopes: list[str]
    justification: str
    ticket_url: str | None
    expires_at: str
    revoked_at: str | None
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, g: JitGrant) -> "GrantOut":
        return cls(
            id=str(g.id),
            user_id=str(g.user_id),
            granted_by_user_id=str(g.granted_by_user_id),
            scopes=list(g.scopes or []),
            justification=g.justification,
            ticket_url=g.ticket_url,
            expires_at=g.expires_at.isoformat(),
            revoked_at=g.revoked_at.isoformat() if g.revoked_at else None,
            is_active=g.is_active and g.expires_at > datetime.now(timezone.utc),
            created_at=g.created_at.isoformat(),
        )


@router.get("", response_model=list[GrantOut])
async def list_grants(
    active: bool = True,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    q = select(JitGrant).where(
        JitGrant.organization_id == uuid.UUID(principal.org_id),
    ).order_by(JitGrant.created_at.desc())
    if active:
        q = q.where(
            JitGrant.is_active.is_(True),
            JitGrant.expires_at > datetime.now(timezone.utc),
        )
    rows = (await session.scalars(q)).all()
    return [GrantOut.from_orm(g) for g in rows]


@router.post("", response_model=GrantOut, status_code=201)
async def create_grant(
    body: GrantIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    if not principal.user_id:
        raise HTTPException(403, "JIT grants must be issued by a human user")

    expires = datetime.now(timezone.utc) + timedelta(minutes=body.duration_minutes)
    g = JitGrant(
        organization_id=uuid.UUID(principal.org_id),
        user_id=uuid.UUID(body.user_id),
        granted_by_user_id=uuid.UUID(principal.user_id),
        scopes=body.scopes,
        justification=body.justification,
        ticket_url=body.ticket_url,
        expires_at=expires,
        is_active=True,
    )
    session.add(g)
    await session.flush()
    await record_admin(
        session,
        org_id=principal.org_id,
        actor=f"user:{principal.email}",
        event_type="access.elevation.granted",
        resource_type="user", resource_id=body.user_id,
        payload={
            "grant_id": str(g.id),
            "scopes": body.scopes,
            "duration_minutes": body.duration_minutes,
            "justification": body.justification,
            "ticket_url": body.ticket_url,
        },
    )
    await emit(session, principal.org_id, "access.elevation.granted", {
        "grant_id": str(g.id), "user_id": body.user_id, "scopes": body.scopes,
        "expires_at": expires.isoformat(),
    })
    await session.commit()
    return GrantOut.from_orm(g)


@router.post("/{grant_id}/revoke", response_model=GrantOut)
async def revoke_grant(
    grant_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    g = await session.get(JitGrant, uuid.UUID(grant_id))
    if not g or str(g.organization_id) != principal.org_id:
        raise HTTPException(404, "Grant not found")
    if not g.is_active:
        raise HTTPException(409, "Grant already inactive")
    g.is_active = False
    g.revoked_at = datetime.now(timezone.utc)
    g.revoked_by_user_id = uuid.UUID(principal.user_id) if principal.user_id else None
    await record_admin(
        session,
        org_id=principal.org_id, actor=f"user:{principal.email}",
        event_type="access.elevation.revoked",
        resource_type="jit_grant", resource_id=grant_id,
        payload={"revoked_at": g.revoked_at.isoformat()},
    )
    await session.commit()
    return GrantOut.from_orm(g)


# ── Self-service elevation request ───────────────────────────────────────────

class ElevationRequestIn(BaseModel):
    scopes: list[str] = Field(..., min_length=1)
    duration_minutes: int = Field(60, ge=5, le=480)
    justification: str = Field(..., min_length=10, max_length=2048)
    ticket_url: str | None = None


class ElevationRequestOut(BaseModel):
    approval_request_id: str
    status: str
    message: str


class MyRequestOut(BaseModel):
    approval_request_id: str
    status: str
    scopes: list[str]
    duration_minutes: int
    justification: str
    ticket_url: str | None
    created_at: str
    expires_at: str
    reviewed_at: str | None
    review_note: str | None


@router.post("/request", response_model=ElevationRequestOut, status_code=202)
async def request_elevation(
    body: ElevationRequestIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Self-service JIT elevation request — any authenticated user.

    Creates a pending ApprovalRequest with request_type="jit_elevation".  An
    admin reviews it via the normal approvals queue; on approval the JitGrant
    is auto-created by ``auto_fulfill_jit_elevation``.
    """
    if not principal.user_id:
        raise HTTPException(403, "JIT elevation requests must come from a human user session")

    metadata: dict[str, Any] = {
        "request_type": "jit_elevation",
        "requested_scopes": body.scopes,
        "duration_minutes": body.duration_minutes,
        "justification": body.justification,
        "ticket_url": body.ticket_url,
        "requester_user_id": principal.user_id,
    }

    approval = ApprovalRequest(
        organization_id=uuid.UUID(principal.org_id),
        subject_type="user",
        subject_id=principal.user_id,
        on_behalf_of_user_id=None,
        action="jit.elevation.request",
        resource_type="jit_grant",
        resource_id=None,
        resource_attrs={},
        context=metadata,
        matched_policy_id=None,
        status="pending",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=24),
    )
    session.add(approval)
    await session.flush()

    await record_admin(
        session,
        org_id=principal.org_id,
        actor=f"user:{principal.user_id}",
        event_type="access.elevation.requested",
        resource_type="approval_request",
        resource_id=str(approval.id),
        payload=metadata,
    )
    await session.commit()

    return ElevationRequestOut(
        approval_request_id=str(approval.id),
        status="pending",
        message="Elevation request submitted. An admin will review it shortly.",
    )


@router.get("/my-requests", response_model=list[MyRequestOut])
async def my_requests(
    status: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """List the calling user's own JIT elevation requests (pending and recent)."""
    if not principal.user_id:
        raise HTTPException(403, "Requires a user session")

    q = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.organization_id == uuid.UUID(principal.org_id),
            ApprovalRequest.subject_type == "user",
            ApprovalRequest.subject_id == principal.user_id,
            ApprovalRequest.action == "jit.elevation.request",
        )
        .order_by(ApprovalRequest.created_at.desc())
        .limit(limit)
    )
    if status:
        q = q.where(ApprovalRequest.status == status)

    rows = (await session.scalars(q)).all()
    result = []
    for r in rows:
        ctx = r.context or {}
        result.append(MyRequestOut(
            approval_request_id=str(r.id),
            status=r.status,
            scopes=ctx.get("requested_scopes", []),
            duration_minutes=ctx.get("duration_minutes", 60),
            justification=ctx.get("justification", ""),
            ticket_url=ctx.get("ticket_url"),
            created_at=r.created_at.isoformat(),
            expires_at=r.expires_at.isoformat(),
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            review_note=r.review_note,
        ))
    return result


# ── Auto-fulfill hook (called by approvals.py on approve) ────────────────────

async def auto_fulfill_jit_elevation(
    session: AsyncSession,
    approval: ApprovalRequest,
    reviewer_user_id: str,
) -> JitGrant | None:
    """If the approval is for a jit_elevation, create the JitGrant automatically.

    Called server-side from approvals.py immediately after the approval row is
    persisted.  Returns the new JitGrant or None if not applicable.
    """
    ctx = approval.context or {}
    if ctx.get("request_type") != "jit_elevation":
        return None

    requester_user_id = ctx.get("requester_user_id") or approval.subject_id
    scopes = ctx.get("requested_scopes") or []
    duration_minutes = int(ctx.get("duration_minutes") or 60)
    justification = ctx.get("justification") or "Approved via self-service JIT request"
    ticket_url = ctx.get("ticket_url")

    expires = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    g = JitGrant(
        organization_id=approval.organization_id,
        user_id=uuid.UUID(requester_user_id),
        granted_by_user_id=uuid.UUID(reviewer_user_id),
        scopes=scopes,
        justification=justification,
        ticket_url=ticket_url,
        expires_at=expires,
        is_active=True,
    )
    session.add(g)
    await session.flush()

    await record_admin(
        session,
        org_id=str(approval.organization_id),
        actor=f"user:{reviewer_user_id}",
        event_type="access.elevation.granted",
        resource_type="user",
        resource_id=requester_user_id,
        payload={
            "grant_id": str(g.id),
            "approval_request_id": str(approval.id),
            "scopes": scopes,
            "duration_minutes": duration_minutes,
            "justification": justification,
            "ticket_url": ticket_url,
        },
    )
    await emit(session, str(approval.organization_id), "access.elevation.granted", {
        "grant_id": str(g.id),
        "user_id": requester_user_id,
        "scopes": scopes,
        "expires_at": expires.isoformat(),
        "via": "self_service_jit",
    })
    return g


# ── Expire due ────────────────────────────────────────────────────────────────

@router.post("/expire-due", include_in_schema=False)
async def expire_due(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Cron-callable: deactivate grants whose expiry has passed."""
    _admin(principal)
    now = datetime.now(timezone.utc)
    rows = (await session.scalars(
        select(JitGrant).where(
            JitGrant.organization_id == uuid.UUID(principal.org_id),
            JitGrant.is_active.is_(True),
            JitGrant.expires_at <= now,
        )
    )).all()
    for g in rows:
        g.is_active = False
        await record_admin(
            session,
            org_id=principal.org_id, actor="system:jit-expirer",
            event_type="access.elevation.expired",
            resource_type="jit_grant", resource_id=str(g.id),
            payload={"scopes": list(g.scopes or [])},
        )
    await session.commit()
    return {"expired": len(rows)}
