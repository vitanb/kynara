"""Cron: expire free-plan trials whose 14-day window has elapsed.

Run daily via Railway cron or any scheduler:
    python -m app.scripts.expire_trials

What it does:
  - Finds Subscriptions where plan="free", status="trialing",
    and current_period_end < now (trial window has passed).
  - Flips status → "active" (they remain on the free tier with limits,
    just the trial badge goes away).
  - Also flips Organization.is_trialing → False so the frontend can
    show an appropriate "upgrade" nudge rather than a trial countdown.

Intentionally soft: we don't cancel access, just remove the trialing flag.
Paid upgrades are handled by Stripe webhooks in billing.py.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models import Organization, Subscription


async def main() -> None:
    now = datetime.now(tz=timezone.utc)

    async with SessionLocal() as session:
        # Find expired trials
        expired = (await session.scalars(
            select(Subscription).where(
                Subscription.plan == "free",
                Subscription.status == "trialing",
                Subscription.current_period_end < now,
            )
        )).all()

        if not expired:
            print("expire_trials: nothing to expire")
            return

        org_ids = [sub.organization_id for sub in expired]

        # Flip subscription status to active (still on free limits, trial just ended)
        await session.execute(
            update(Subscription)
            .where(
                Subscription.plan == "free",
                Subscription.status == "trialing",
                Subscription.current_period_end < now,
            )
            .values(status="active")
        )

        # Flip org.is_trialing flag so the frontend upgrade nudge shows
        await session.execute(
            update(Organization)
            .where(Organization.id.in_(org_ids))
            .values(is_trialing=False)
        )

        await session.commit()
        print(f"expire_trials: expired {len(expired)} trial(s) — org IDs: {[str(o) for o in org_ids]}")


if __name__ == "__main__":
    asyncio.run(main())
