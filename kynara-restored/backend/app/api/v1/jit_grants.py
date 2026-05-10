"""Just-in-Time (JIT) grant endpoints.

A JIT grant is a time-bound elevation of a user's effective scopes. Used for
break-glass scenarios: "give me ``crm:write`` for 2 hours to debug a prod
escalation." Every grant carries a justification and a link to the originating
ticket. Every grant create/revoke is recorded in the audit chain.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
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
