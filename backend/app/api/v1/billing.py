"""Billing: subscription status, checkout, usage summary, Stripe webhook."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request

logger = logging.getLogger("billing.api")
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, require_seat
from app.billing import stripe_service
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Invoice, Organization, Subscription, UsageRecord
from app.models.agent import Agent

router = APIRouter(prefix="/billing", tags=["billing"])

# Quotas applied when a plan activates via Stripe webhook.
_PLAN_QUOTAS: dict[str, dict] = {
    "free":       {"seats_included": 3,       "decisions_included": 10_000},
    "trial":      {"seats_included": 5,       "decisions_included": 100_000},
    "pro":        {"seats_included": 10,      "decisions_included": 50_000},
    "enterprise": {"seats_included": 999_999, "decisions_included": 10_000_000},
}


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


@router.get("/attribution", summary="Decision cost attribution by project / team / cost_centre")
async def get_attribution(
    principal: Principal = Depends(require_seat("owner", "admin", "auditor")),
    session: AsyncSession = Depends(_session),
    group_by: str = "project",  # project | team | cost_centre
):
    """Return decision counts and estimated overage cost broken down by agent tag.

    Useful for internal chargeback: which project / team is consuming the most
    decisions and driving overage costs this billing period?

    Query params:
        group_by: one of ``project``, ``team``, ``cost_centre`` (default: project)
    """
    if group_by not in ("project", "team", "cost_centre"):
        from fastapi import HTTPException
        raise HTTPException(400, "group_by must be one of: project, team, cost_centre")

    org_id = uuid.UUID(principal.org_id)

    # Get current billing period from subscription
    sub = await session.scalar(
        select(Subscription).where(Subscription.organization_id == org_id)
    )
    now = datetime.now(tz=timezone.utc)
    period_start = (sub.current_period_start if sub and sub.current_period_start
                    else now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    period_end = (sub.current_period_end if sub and sub.current_period_end
                  else period_start + timedelta(days=30))
    rate = sub.overage_cents_per_1k if sub else 50
    included = sub.decisions_included if sub else 0

    # Get all agents for the org with their tag
    agents = (await session.scalars(
        select(Agent).where(Agent.organization_id == org_id)
    )).all()

    # Build agent_id → tag mapping
    tag_map: dict[str, str] = {}
    for a in agents:
        tag = getattr(a, group_by, None) or "untagged"
        tag_map[str(a.id)] = tag

    # Sum decisions per agent in the current period
    usage_rows = (await session.execute(
        select(
            func.cast(
                func.jsonb_extract_path_text(UsageRecord.dims.cast(sa.Text), "agent_id"),
                sa.String
            ).label("agent_id"),
            func.sum(UsageRecord.quantity).label("decisions"),
        )
        .where(
            UsageRecord.organization_id == org_id,
            UsageRecord.metric == "decisions",
            UsageRecord.ts >= period_start,
            UsageRecord.ts < period_end,
        )
        .group_by("agent_id")
    )).all()

    # Roll up by tag
    totals: dict[str, int] = {}
    for row in usage_rows:
        agent_id = row.agent_id or ""
        tag = tag_map.get(agent_id, "untagged")
        totals[tag] = totals.get(tag, 0) + int(row.decisions or 0)

    org_total = sum(totals.values())
    result = []
    for tag, decisions in sorted(totals.items(), key=lambda x: -x[1]):
        pct = round(decisions / org_total * 100, 1) if org_total else 0.0
        overage = max(0, decisions - included) if len(totals) == 1 else 0
        result.append({
            group_by: tag,
            "decisions": decisions,
            "pct_of_total": pct,
            "estimated_overage_cents": overage * rate // 1000,
        })

    return {
        "group_by": group_by,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "org_total_decisions": org_total,
        "breakdown": result,
    }


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


@router.post("/portal")
async def customer_portal(
    request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Return a Stripe Customer Portal URL so the user can manage their subscription."""
    sub = await session.scalar(select(Subscription).where(
        Subscription.organization_id == uuid.UUID(principal.org_id)
    ))
    customer_id = sub.stripe_customer_id if sub else None
    if not customer_id:
        # Try to look up customer by org metadata if we don't have it cached
        raise HTTPException(503, "No Stripe customer found for this organisation. "
                                 "Complete a checkout first.")
    try:
        url = stripe_service.create_portal_session(
            customer_id=customer_id,
            return_url=f"{request.headers.get('origin', '')}/app/billing",
        )
    except RuntimeError:
        raise HTTPException(503, "Billing not configured")
    return {"redirect_url": url}


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

    if etype == "checkout.session.completed":
        # This is the authoritative moment a customer completes payment.
        # metadata.plan was set when we created the checkout session.
        plan_name = data.get("metadata", {}).get("plan")
        if plan_name:
            sub.plan = plan_name
            sub.status = "active"
            # Persist the Stripe customer ID so we can open the portal later
            if data.get("customer"):
                sub.stripe_customer_id = data["customer"]
            # Apply seats + decisions quota for the new plan
            quotas = _PLAN_QUOTAS.get(plan_name, {})
            if quotas:
                sub.seats_included = quotas["seats_included"]
                sub.decisions_included = quotas["decisions_included"]
            # Also update org.plan so quota enforcement sees the new tier
            org = await session.scalar(
                select(Organization).where(Organization.id == uuid.UUID(org_id))
            )
            if org:
                org.plan = plan_name
            logger.info(
                "checkout.session.completed org=%s plan=%s seats=%s decisions=%s → active",
                org_id, plan_name,
                quotas.get("seats_included"), quotas.get("decisions_included"),
            )

    elif etype.startswith("customer.subscription."):
        new_status = data.get("status", sub.status)
        sub.status = new_status
        sub.stripe_subscription_id = data.get("id")
        sub.current_period_start = datetime.fromtimestamp(data["current_period_start"], tz=timezone.utc) \
            if data.get("current_period_start") else None
        sub.current_period_end = datetime.fromtimestamp(data["current_period_end"], tz=timezone.utc) \
            if data.get("current_period_end") else None
        sub.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
        # Capture the Stripe Subscription Item ID (si_xxxx) from the first line item.
        # This is required for the nightly usage reporter to call create_usage_record().
        items = data.get("items", {}).get("data", [])
        if items and not sub.stripe_subscription_item_id:
            sub.stripe_subscription_item_id = items[0].get("id")
        # Sync past_due_since: stamp on first transition to past_due; clear when recovered.
        if new_status == "past_due" and sub.past_due_since is None:
            sub.past_due_since = datetime.now(tz=timezone.utc)
            logger.warning(
                "customer.subscription status=past_due org=%s — grace period starts now",
                org_id,
            )
        elif new_status != "past_due":
            sub.past_due_since = None

    elif etype == "invoice.paid":
        # Reset to active on successful payment (recovers from past_due)
        if sub.status == "past_due":
            sub.status = "active"
            sub.past_due_since = None  # clear grace-period stamp
            logger.info("invoice.paid org=%s — subscription recovered from past_due", org_id)
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
        # Flip to past_due — grace period begins; policy engine enforces after 7 days
        sub.status = "past_due"
        if sub.past_due_since is None:
            sub.past_due_since = datetime.now(tz=timezone.utc)
        logger.warning(
            "invoice.payment_failed org=%s -- subscription marked past_due (grace period starts %s)",
            org_id, sub.past_due_since.isoformat(),
        )

    await session.commit()
    await record_admin(
        session, org_id=org_id, actor="system",
        event_type=f"billing.{etype}",
        resource_type="subscription", resource_id=str(sub.id),
        payload={"stripe_event_id": event.get("id"), "status": sub.status},
    )
    return {"ok": True}
