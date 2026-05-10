"""Webhook subscription management endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import WebhookEndpoint, WebhookOutbox
from app.webhooks.service import WebhookService, EVENT_TYPES

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _admin(p: Principal):
    if p.seat_role not in ("owner", "admin"):
        raise HTTPException(403, "Requires owner or admin role")


class EndpointIn(BaseModel):
    url: HttpUrl
    event_types: list[str]
    description: str | None = None


class EndpointOut(BaseModel):
    id: str
    url: str
    description: str | None
    event_types: list[str]
    is_enabled: bool
    secret_prefix: str
    last_success_at: str | None
    last_failure_at: str | None
    consecutive_failures: int
    created_at: str

    @classmethod
    def from_orm(cls, e: WebhookEndpoint) -> "EndpointOut":
        return cls(
            id=str(e.id),
            url=e.url,
            description=e.description,
            event_types=list(e.event_types or []),
            is_enabled=e.is_enabled,
            secret_prefix=e.secret_prefix,
            last_success_at=e.last_success_at.isoformat() if e.last_success_at else None,
            last_failure_at=e.last_failure_at.isoformat() if e.last_failure_at else None,
            consecutive_failures=e.consecutive_failures,
            created_at=e.created_at.isoformat(),
        )


class FreshSecretOut(EndpointOut):
    secret: str  # plaintext, shown only once on create / rotate


class DeliveryOut(BaseModel):
    id: str
    event_id: str
    event_type: str
    status: str
    attempts: int
    last_response_status: int | None
    last_error: str | None
    last_attempt_at: str | None
    delivered_at: str | None
    created_at: str


@router.get("/event-types")
async def list_event_types():
    return {"event_types": list(EVENT_TYPES)}


@router.get("", response_model=list[EndpointOut])
async def list_endpoints(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.organization_id == uuid.UUID(principal.org_id))
        .order_by(WebhookEndpoint.created_at.desc())
    )).all()
    return [EndpointOut.from_orm(r) for r in rows]


@router.post("", response_model=FreshSecretOut, status_code=201)
async def create_endpoint(
    body: EndpointIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    svc = WebhookService(session)
    try:
        ep, secret = await svc.create_endpoint(
            org_id=principal.org_id,
            url=str(body.url),
            event_types=body.event_types,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    await session.commit()
    out = EndpointOut.from_orm(ep).model_dump()
    out["secret"] = secret
    return FreshSecretOut(**out)


@router.delete("/{endpoint_id}", status_code=204)
async def delete_endpoint(
    endpoint_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    ep = await session.get(WebhookEndpoint, uuid.UUID(endpoint_id))
    if not ep or str(ep.organization_id) != principal.org_id:
        raise HTTPException(404, "Endpoint not found")
    await session.delete(ep)
    await session.commit()


@router.post("/{endpoint_id}/rotate-secret", response_model=FreshSecretOut)
async def rotate_secret(
    endpoint_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    ep = await session.get(WebhookEndpoint, uuid.UUID(endpoint_id))
    if not ep or str(ep.organization_id) != principal.org_id:
        raise HTTPException(404, "Endpoint not found")
    svc = WebhookService(session)
    secret = await svc.rotate_secret(ep)
    await session.commit()
    out = EndpointOut.from_orm(ep).model_dump()
    out["secret"] = secret
    return FreshSecretOut(**out)


@router.get("/{endpoint_id}/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    endpoint_id: str,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    q = (
        select(WebhookOutbox)
        .where(
            WebhookOutbox.organization_id == uuid.UUID(principal.org_id),
            WebhookOutbox.endpoint_id == uuid.UUID(endpoint_id),
        )
        .order_by(WebhookOutbox.created_at.desc())
        .limit(limit)
    )
    if status:
        q = q.where(WebhookOutbox.status == status)
    rows = (await session.scalars(q)).all()
    return [
        DeliveryOut(
            id=str(r.id),
            event_id=r.event_id,
            event_type=r.event_type,
            status=r.status,
            attempts=r.attempts,
            last_response_status=r.last_response_status,
            last_error=r.last_error,
            last_attempt_at=r.last_attempt_at.isoformat() if r.last_attempt_at else None,
            delivered_at=r.delivered_at.isoformat() if r.delivered_at else None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/{endpoint_id}/deliveries/{delivery_id}/replay", status_code=202)
async def replay_delivery(
    endpoint_id: str,
    delivery_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Re-queue a failed/dead delivery for another attempt."""
    _admin(principal)
    row = await session.get(WebhookOutbox, uuid.UUID(delivery_id))
    if not row or str(row.organization_id) != principal.org_id:
        raise HTTPException(404, "Delivery not found")
    if str(row.endpoint_id) != endpoint_id:
        raise HTTPException(400, "Delivery does not belong to this endpoint")
    row.status = "pending"
    row.attempts = 0
    row.last_error = None
    await session.commit()
    return {"queued": True}


@router.get("/stats")
async def stats(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Webhook health rollup for the dashboard."""
    org = uuid.UUID(principal.org_id)
    rows = await session.execute(
        select(WebhookOutbox.status, func.count())
        .where(WebhookOutbox.organization_id == org)
        .group_by(WebhookOutbox.status)
    )
    counts = {s: c for s, c in rows.all()}
    return {
        "delivered": counts.get("delivered", 0),
        "pending": counts.get("pending", 0),
        "failed": counts.get("failed", 0),
        "dead": counts.get("dead", 0),
    }
