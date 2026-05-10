"""Quota enforcement helpers — seat limits, decision quotas, trial expiry.

All functions are async and accept an AsyncSession so they compose cleanly
with existing endpoint dependencies.  Raise HTTP 402 when a limit is
exceeded so the frontend can surface a clear upgrade prompt.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrgMembership, Subscription, UsageRecord


# ------------------------------------------------------------------ helpers --

async def get_subscription(session: AsyncSession, org_id: str) -> Subscription | None:
    return await session.scalar(
        select(Subscription).where(
            Subscription.organization_id == uuid.UUID(org_id)
        )
    )


async def count_current_seats(session: AsyncSession, org_id: str) -> int:
    result = await session.scalar(
        select(func.count()).where(
            OrgMembership.organization_id == uuid.UUID(org_id)
        )
    )
    return int(result or 0)


async def count_monthly_decisions(session: AsyncSession, org_id: str) -> int:
    """Count decision usage records in the current UTC calendar month."""
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.scalar(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
            UsageRecord.organization_id == uuid.UUID(org_id),
            UsageRecord.metric == "decisions",
            UsageRecord.ts >= month_start,
        )
    )
    return int(result or 0)


# ------------------------------------------------------------------ checks --

async def enforce_seat_limit(session: AsyncSession, org_id: str) -> None:
    """Raise 402 if adding one more seat would exceed the plan limit."""
    sub = await get_subscription(session, org_id)
    if not sub:
        return  # no subscription row → unlimited (edge case; shouldn't happen post-signup)

    # Paid plans (non-free) are managed by Stripe seat counts — don't block here
    if sub.plan != "free":
        return

    current = await count_current_seats(session, org_id)
    if current >= sub.seats_included:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Seat limit reached: your free plan includes {sub.seats_included} seat(s) "
                f"and you already have {current}. Upgrade to add more members."
            ),
        )


async def enforce_decision_quota(session: AsyncSession, org_id: str) -> None:
    """Raise 402 if the org has consumed its monthly decision quota."""
    sub = await get_subscription(session, org_id)
    if not sub:
        return

    if sub.plan != "free":
        return  # paid plans are metered by Stripe — no hard block here

    used = await count_monthly_decisions(session, org_id)
    if used >= sub.decisions_included:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Monthly decision quota reached: your free plan includes "
                f"{sub.decisions_included:,} decisions per month and you have used {used:,}. "
                "Upgrade to continue making policy decisions."
            ),
        )


async def enforce_active_subscription(session: AsyncSession, org_id: str) -> None:
    """Raise 402 if the org's subscription is in a blocked state (canceled, expired)."""
    sub = await get_subscription(session, org_id)
    if not sub:
        return
    if sub.status in ("canceled", "incomplete_expired"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your subscription has ended. Please renew to continue using Kynara.",
        )


# ----------------------------------------------------------------- recording --

async def record_decision(
    session: AsyncSession,
    org_id: str,
    effect: str,
    agent_id: str | None = None,
) -> None:
    """Append a usage record for one policy decision (fire-and-forget in endpoint)."""
    dims: dict = {"effect": effect}
    if agent_id:
        dims["agent_id"] = agent_id
    session.add(
        UsageRecord(
            organization_id=uuid.UUID(org_id),
            ts=datetime.now(tz=timezone.utc),
            metric="decisions",
            quantity=1,
            dims=dims,
        )
    )
    # Caller must commit (the endpoint already does this or sqlalchemy flushes on close)
