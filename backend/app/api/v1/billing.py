"""Billing: subscription status, checkout, usage summary, Stripe webhook."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request

logger = logging.getLogger("billing.api")
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, require_seat
from app.billing import stripe_service
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Invoice, Subscription, UsageRecord

router = APIRouter(prefix="/billing", tags=["billing"])


async def _session():
    async with SessionLocal() as s:
        yield s


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    seats_included: int
    decisions_included: int
    current_period_start: datetime | None
    current_period_end: datetime | None


class UsageOut(BaseModel):
    period_start: datetime
    period_end: datetime
    decisions_used: int
    decisions_included: int
    overage_decisions: int
    overage_amount_cents: int


class CheckoutIn(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


@router.get("/subscription", response_model=SubscriptionOut)
async def get_sub(principal: Principal = Depends(require_seat("owner", "admin", "auditor")),
                  session: AsyncSession = Depends(_session)):
    s = await session.scalar(select(Subscription).where(
        Subscription.organization_id == uuid.UUID(principal.org_id)
    ))
    if not s:
        raise HTTPException(404, "No subscription")
    return SubscriptionOut(
        plan=s.plan, status=s.status,
        seats_included=s.seats_included, decisions_included=s.decisions_included,
        current_period_start=s.current_period_start, current_period_end=s.current_period_end,
    )


@router.get("/usage", response_model=UsageOut)
async def get_usage(principal: Principal = Depends(require_seat("owner", "admin", "auditor")),
                    session: AsyncSession = Depends(_session)):
    now = datetime.now(tz=timezone.utc)
    sub = await session.scalar(select(Subscription).where(
        Subscription.organization_id == uuid.UUID(principal.org_id)
    ))
    start = (sub.current_period_start if sub and sub.current_period_start
             else now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    end = sub.current_period_end if sub and sub.current_period_end else (start + timedelta(days=30))

    used = await session.scalar(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.organization_id == uuid.UUID(principal.org_id),
            UsageRecord.metric == "decisions",
            UsageRecord.ts >= start,
            UsageRecord.ts < end,
        )
    ) or 0
    included = sub.decisions_included if sub else 0
    overage = max(0, int(used) - included)
    rate = sub.overage_cents_per_1k if sub else 50
    return UsageOut(
        period_start=start, period_end=end,
        decisions_used=int(used), decisions_included=included,
        overage_decisions=overage, overage_amount_cents=overage * rate // 1000,
    )


@router.get("/invoices")
async def list_invoices(
    principal: Principal = Depends(require_seat("owner", "admin", "auditor")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(Invoice)
        .where(Invoice.organization_id == uuid.UUID(principal.org_id))
        .order_by(Invoice.period_start.desc())
        .limit(24)
    )).all()
    return [
        {
            "id": str(r.id),
            "amount_cents": r.amount_cents,
            "currency": r.currency,
            "status": r.status,
            "hosted_url": r.hosted_url,
            "pdf_url": r.pdf_url,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
        }
        for r in rows
    ]


@router.post("/checkout")
async def checkout(body: CheckoutIn, request: Request,
                   principal: Principal = Depends(require_seat("owner", "admin")),
                   session: AsyncSession = Depends(_session)):
    try:
        url = stripe_service.create_checkout_session(
            org_id=principal.org_id,
            plan=body.plan,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except RuntimeError:
        raise HTTPException(503, "Billing not configured")
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="billing.checkout.started",
        resource_type="subscription", resource_id="pending",
        payload={"plan": body.plan},
        ip_address=request.client.host if request.client else None,
    )
    return {"redirect_url": url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    session: AsyncSession = Depends(_session),
):
    body = await request.body()
    try:
        event = stripe_service.verify_webhook(body, stripe_signature or "")
    except PermissionError:
        raise HTTPException(400, "Invalid signature")

    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    org_id = data.get("metadata", {}).get("org_id") or data.get("client_reference_id")
    if not org_id:
        return {"ok": True}

    sub = await session.scalar(select(Subscription).where(
        Subscription.organization_id == uuid.UUID(org_id)
    ))
    if not sub:
        sub = Subscription(organization_id=uuid.UUID(org_id))
        session.add(sub)

    if etype.startswith("customer.subscription."):
        sub.status = data.get("status", sub.status)
        sub.stripe_subscription_id = data.get("id")
        sub.current_period_start = datetime.fromtimestamp(data["current_period_start"], tz=timezone.utc) \
            if data.get("current_period_start") else None
        sub.current_period_end = datetime.fromtimestamp(data["current_period_end"], tz=timezone.utc) \
            if data.get("current_period_end") else None
        sub.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    elif etype == "invoice.paid":
        # Reset to active on successful payment (recovers from past_due)
        if sub.status == "past_due":
            sub.status = "active"
        session.add(Invoice(
            organization_id=uuid.UUID(org_id),
            stripe_invoice_id=data["id"],
            amount_cents=data["amount_paid"],
            currency=data.get("currency", "usd"),
            status="paid",
            hosted_url=data.get("hosted_invoice_url"),
            pdf_url=data.get("invoice_pdf"),
            period_start=datetime.fromtimestamp(data["period_start"], tz=timezone.utc),
            period_end=datetime.fromtimestamp(data["period_end"], tz=timezone.utc),
        ))
    elif etype == "invoice.payment_failed":
        # Flip to past_due — policy engine will start denying decisions for this org
        sub.status = "past_due"
        logger.warning("invoice.payment_failed org=%s — subscription marked past_due", org_id)

    await session.commit()
    await record_admin(
        session, org_id=org_id, actor="system",
        event_type=f"billing.{etype}",
        resource_type="subscription", resource_id=str(sub.id),
        payload={"stripe_event_id": event.get("id"), "status": sub.status},
    )
    return {"ok": True}
