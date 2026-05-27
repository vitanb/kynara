"""Nightly Stripe metered-usage reporter.

Invoked by the Helm CronJob every night at 02:00 UTC:
    python -m app.scripts.report_billing_usage

For every paid organisation that has a ``stripe_subscription_item_id`` (the
``si_xxxx`` token captured from the Stripe subscription webhook), this script:

1. Sums all ``decisions`` usage records in the current billing period.
2. Sums all ``stripe_reported`` records for the same period to find how much
   has already been reported to Stripe.
3. Reports the *net new* quantity via ``stripe.SubscriptionItem.create_usage_record()``
   using ``action="increment"``.
4. Writes a ``UsageRecord(metric="stripe_reported", quantity=<net_new>)`` so the
   next run does not double-report.

Free and trial plans are skipped — they are hard-capped by ``enforce_decision_quota()``
and are not metered on Stripe.

Exits 0 on success (even if some orgs failed — failures are logged individually),
1 only if the entire run crashes before processing any orgs.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.billing import stripe_service
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import Organization, Subscription, UsageRecord

log = get_logger("report_billing_usage")

# Plans that are metered on Stripe (have a subscription item to report to)
_METERED_PLANS = {"pro", "enterprise"}


async def _report_org(
    session,
    sub: Subscription,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
) -> dict:
    """Report net-new decisions for one org. Returns a result dict for logging."""
    org_id = str(sub.organization_id)

    # Sum decisions in the current billing period
    decisions_used = int(
        await session.scalar(
            select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
                UsageRecord.organization_id == sub.organization_id,
                UsageRecord.metric == "decisions",
                UsageRecord.ts >= period_start,
                UsageRecord.ts < period_end,
            )
        )
        or 0
    )

    # Sum what we've already reported to Stripe this period
    already_reported = int(
        await session.scalar(
            select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
                UsageRecord.organization_id == sub.organization_id,
                UsageRecord.metric == "stripe_reported",
                UsageRecord.ts >= period_start,
                UsageRecord.ts < period_end,
            )
        )
        or 0
    )

    net_new = decisions_used - already_reported
    if net_new <= 0:
        log.info(
            "report_billing_usage.skip",
            org_id=org_id,
            decisions_used=decisions_used,
            already_reported=already_reported,
            reason="nothing_new",
        )
        return {"org_id": org_id, "net_new": 0, "status": "skipped"}

    # Report to Stripe
    stripe_service.report_usage(
        subscription_item_id=sub.stripe_subscription_item_id,
        quantity=net_new,
        ts=int(now.timestamp()),
    )

    # Record what we just reported so the next run doesn't double-count
    session.add(
        UsageRecord(
            organization_id=sub.organization_id,
            ts=now,
            metric="stripe_reported",
            quantity=net_new,
            dims={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "decisions_used": decisions_used,
            },
        )
    )

    log.info(
        "report_billing_usage.reported",
        org_id=org_id,
        net_new=net_new,
        decisions_used=decisions_used,
        already_reported=already_reported,
        stripe_item=sub.stripe_subscription_item_id,
    )
    return {"org_id": org_id, "net_new": net_new, "status": "reported"}


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    t0 = time.perf_counter()
    now = datetime.now(tz=timezone.utc)
    log.info("report_billing_usage.start", ts=now.isoformat())

    try:
        reported = 0
        skipped = 0
        errors = 0

        async with SessionLocal() as session:
            # Fetch all paid subscriptions that have a stripe subscription item id
            subs = (
                await session.scalars(
                    select(Subscription).where(
                        Subscription.plan.in_(_METERED_PLANS),
                        Subscription.status.in_(("active", "past_due")),
                        Subscription.stripe_subscription_item_id.isnot(None),
                    )
                )
            ).all()

            log.info("report_billing_usage.orgs_to_process", count=len(subs))

            for sub in subs:
                try:
                    # Determine billing period: use Stripe period if available,
                    # otherwise fall back to the current UTC calendar month.
                    if sub.current_period_start and sub.current_period_end:
                        period_start = sub.current_period_start
                        period_end = sub.current_period_end
                    else:
                        period_start = now.replace(
                            day=1, hour=0, minute=0, second=0, microsecond=0
                        )
                        # Approximate: next month's first day
                        if period_start.month == 12:
                            period_end = period_start.replace(year=period_start.year + 1, month=1)
                        else:
                            period_end = period_start.replace(month=period_start.month + 1)

                    result = await _report_org(session, sub, period_start, period_end, now)
                    if result["status"] == "reported":
                        reported += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    errors += 1
                    log.exception(
                        "report_billing_usage.org_error",
                        org_id=str(sub.organization_id),
                        error=str(exc),
                    )

            await session.commit()

        elapsed = round(time.perf_counter() - t0, 3)
        log.info(
            "report_billing_usage.complete",
            reported=reported,
            skipped=skipped,
            errors=errors,
            elapsed_s=elapsed,
        )
        return 0
    except Exception as exc:
        log.exception("report_billing_usage.fatal", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
