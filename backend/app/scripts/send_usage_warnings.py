"""Daily usage-warning email sender.

Invoked by the Helm CronJob once per day at 08:00 UTC:
    python -m app.scripts.send_usage_warnings

For every organisation, checks whether monthly decision usage has crossed the
80 % or 100 % threshold and sends a warning email to the org owner(s) if it
hasn't been sent yet this billing period:

  * 80 % threshold → "approaching limit" email  (metric: ``email_warning_80pct``)
  * 100 % threshold → "limit reached" email      (metric: ``email_warning_100pct``)

Deduplication is handled by querying UsageRecord for the sentinel metrics above,
so re-running the job after a crash is safe — no duplicate emails.

Exits 0 on success, 1 on fatal error.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.email import send_email, _base_html
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import OrgMembership, Organization, Subscription, UsageRecord

log = get_logger("send_usage_warnings")

_THRESHOLD_80 = 0.80
_THRESHOLD_100 = 1.00


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

def _warning_80_html(org_name: str, used: int, included: int, pct: float, portal_url: str) -> str:
    content = f"""
<h2 style="color:#F59E0B;margin:0 0 16px">Usage Alert: {pct:.0f}% of monthly limit reached</h2>
<p style="color:#CBD5E1;margin:0 0 12px">
  Your organisation <strong style="color:#F8FAFC">{org_name}</strong> has used
  <strong style="color:#F59E0B">{used:,} of {included:,} decisions</strong>
  ({pct:.1f}%) included in your current billing period.
</p>
<p style="color:#CBD5E1;margin:0 0 20px">
  At the current rate you may reach your limit before the period ends.
  Upgrading now ensures uninterrupted service for your AI agents.
</p>
<a href="{portal_url}"
   style="display:inline-block;background:#1A56A8;color:#fff;
          padding:12px 24px;border-radius:6px;text-decoration:none;
          font-weight:600;font-size:14px">
  View Billing &amp; Upgrade
</a>
<p style="color:#64748B;font-size:12px;margin:24px 0 0">
  You can manage your subscription and view detailed usage in the
  <a href="{portal_url}" style="color:#60A5FA">Kynara billing portal</a>.
  Paid plans include metered overage at $0.50 per 1,000 additional decisions
  so your agents will never be blocked unexpectedly.
</p>
"""
    return _base_html(content)


def _warning_100_html(org_name: str, used: int, included: int, portal_url: str) -> str:
    content = f"""
<h2 style="color:#EF4444;margin:0 0 16px">Usage Limit Reached</h2>
<p style="color:#CBD5E1;margin:0 0 12px">
  Your organisation <strong style="color:#F8FAFC">{org_name}</strong> has consumed all
  <strong style="color:#EF4444">{included:,} decisions</strong> included in your current
  billing period ({used:,} used).
</p>
<p style="color:#CBD5E1;margin:0 0 8px">
  <strong style="color:#F8FAFC">Free plan:</strong> further policy decisions will be
  blocked until the next billing period or until you upgrade.
</p>
<p style="color:#CBD5E1;margin:0 0 20px">
  <strong style="color:#F8FAFC">Paid plan:</strong> additional decisions are metered
  at $0.50 per 1,000 — your agents will continue running uninterrupted.
</p>
<a href="{portal_url}"
   style="display:inline-block;background:#EF4444;color:#fff;
          padding:12px 24px;border-radius:6px;text-decoration:none;
          font-weight:600;font-size:14px">
  Upgrade Now
</a>
<p style="color:#64748B;font-size:12px;margin:24px 0 0">
  Visit the <a href="{portal_url}" style="color:#60A5FA">Kynara billing portal</a>
  to upgrade your plan or review your usage history.
</p>
"""
    return _base_html(content)


def _warning_80_text(org_name: str, used: int, included: int, pct: float, portal_url: str) -> str:
    return (
        f"Usage Alert for {org_name}: {pct:.1f}% of monthly limit reached\n\n"
        f"You have used {used:,} of {included:,} decisions ({pct:.1f}%) this billing period.\n\n"
        f"Upgrade to avoid service interruption: {portal_url}\n"
    )


def _warning_100_text(org_name: str, used: int, included: int, portal_url: str) -> str:
    return (
        f"Usage Limit Reached for {org_name}\n\n"
        f"You have used all {included:,} decisions included in this billing period ({used:,} used).\n\n"
        f"Upgrade now to restore service: {portal_url}\n"
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

async def _owner_emails(session, org_id) -> list[str]:
    """Return email addresses of all owners/admins of the organisation."""
    rows = (
        await session.scalars(
            select(OrgMembership).where(
                OrgMembership.organization_id == org_id,
                OrgMembership.role.in_(("owner", "admin")),
                OrgMembership.status == "active",
            )
        )
    ).all()
    # Each OrgMembership has a user_id; we need the user's email.
    # Import here to avoid circular imports at module level.
    from app.models.user import User  # noqa: PLC0415

    emails: list[str] = []
    for m in rows:
        email = await session.scalar(
            select(User.email).where(User.id == m.user_id)
        )
        if email:
            emails.append(email)
    return emails


async def _already_sent(session, org_id, metric: str, period_start: datetime) -> bool:
    count = await session.scalar(
        select(func.count()).where(
            UsageRecord.organization_id == org_id,
            UsageRecord.metric == metric,
            UsageRecord.ts >= period_start,
        )
    )
    return int(count or 0) > 0


async def _mark_sent(session, org_id, metric: str, now: datetime, extra_dims: dict) -> None:
    session.add(
        UsageRecord(
            organization_id=org_id,
            ts=now,
            metric=metric,
            quantity=1,
            dims=extra_dims,
        )
    )


async def _process_org(session, sub: Subscription, org: Organization, now: datetime) -> dict:
    org_id = sub.organization_id
    org_id_str = str(org_id)
    settings = get_settings()
    portal_url = f"{settings.app_url}/billing"

    # Determine period boundaries
    if sub.current_period_start and sub.current_period_end:
        period_start = sub.current_period_start
        period_end = sub.current_period_end
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)

    # Count decisions this period
    used = int(
        await session.scalar(
            select(func.coalesce(func.sum(UsageRecord.quantity), 0)).where(
                UsageRecord.organization_id == org_id,
                UsageRecord.metric == "decisions",
                UsageRecord.ts >= period_start,
                UsageRecord.ts < period_end,
            )
        )
        or 0
    )

    included = sub.decisions_included
    if included <= 0:
        return {"org_id": org_id_str, "status": "skipped", "reason": "no_quota"}

    pct = used / included

    emails = await _owner_emails(session, org_id)
    if not emails:
        log.warning("send_usage_warnings.no_owners", org_id=org_id_str)
        return {"org_id": org_id_str, "status": "skipped", "reason": "no_owners"}

    sent: list[str] = []

    # 100% threshold — check first so we don't double-send the 80% email
    if pct >= _THRESHOLD_100:
        if not await _already_sent(session, org_id, "email_warning_100pct", period_start):
            for email in emails:
                await send_email(
                    to=email,
                    subject=f"[Kynara] Usage limit reached — {org.name}",
                    html_body=_warning_100_html(org.name, used, included, portal_url),
                    text_body=_warning_100_text(org.name, used, included, portal_url),
                )
            await _mark_sent(
                session, org_id, "email_warning_100pct", now,
                {"used": used, "included": included, "pct": round(pct, 4)},
            )
            sent.append("100pct")
            log.info(
                "send_usage_warnings.sent",
                org_id=org_id_str, threshold="100pct",
                used=used, included=included, recipients=len(emails),
            )

    # 80% threshold (only if not yet at 100%)
    elif pct >= _THRESHOLD_80:
        if not await _already_sent(session, org_id, "email_warning_80pct", period_start):
            for email in emails:
                await send_email(
                    to=email,
                    subject=f"[Kynara] Approaching usage limit ({pct:.0f}%) — {org.name}",
                    html_body=_warning_80_html(org.name, used, included, pct * 100, portal_url),
                    text_body=_warning_80_text(org.name, used, included, pct * 100, portal_url),
                )
            await _mark_sent(
                session, org_id, "email_warning_80pct", now,
                {"used": used, "included": included, "pct": round(pct, 4)},
            )
            sent.append("80pct")
            log.info(
                "send_usage_warnings.sent",
                org_id=org_id_str, threshold="80pct",
                used=used, included=included, pct=round(pct * 100, 1),
                recipients=len(emails),
            )

    if not sent:
        return {"org_id": org_id_str, "status": "below_threshold", "pct": round(pct * 100, 1)}

    return {"org_id": org_id_str, "status": "sent", "thresholds": sent}


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    t0 = time.perf_counter()
    now = datetime.now(tz=timezone.utc)
    log.info("send_usage_warnings.start", ts=now.isoformat())

    try:
        sent_count = 0
        skipped_count = 0
        error_count = 0

        async with SessionLocal() as session:
            # Join subscriptions → organisations; skip free orgs with tiny quotas
            # (they already get HTTP 402 — no need to warn them separately unless desired)
            rows = (
                await session.execute(
                    select(Subscription, Organization).join(
                        Organization,
                        Organization.id == Subscription.organization_id,
                    ).where(
                        Subscription.status.in_(("active", "trialing", "past_due")),
                    )
                )
            ).all()

            log.info("send_usage_warnings.orgs_to_check", count=len(rows))

            for sub, org in rows:
                try:
                    result = await _process_org(session, sub, org, now)
                    if result.get("status") == "sent":
                        sent_count += 1
                    else:
                        skipped_count += 1
                except Exception as exc:
                    error_count += 1
                    log.exception(
                        "send_usage_warnings.org_error",
                        org_id=str(sub.organization_id),
                        error=str(exc),
                    )

            await session.commit()

        elapsed = round(time.perf_counter() - t0, 3)
        log.info(
            "send_usage_warnings.complete",
            sent=sent_count,
            skipped=skipped_count,
            errors=error_count,
            elapsed_s=elapsed,
        )
        return 0
    except Exception as exc:
        log.exception("send_usage_warnings.fatal", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
