"""JIT grant expiry cron entrypoint.

Invoked by the Helm CronJob every 2 minutes:
    python -m app.scripts.expire_jit_grants

Finds all JIT grants whose ``expires_at`` has passed and ``is_active`` is still
True, deactivates them, and writes an ``access.elevation.expired`` audit event
for each one so the audit trail is complete.

The policy decision engine checks ``is_active`` + ``expires_at`` at runtime, so
an agent or user whose grant expired will be denied on the very next decision
call — but this job ensures the database record is clean and the audit event
is written promptly for compliance dashboards and SIEM forwarding.

Exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import asyncio
import sys
import time

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.jit_grant import JitGrant
from app.audit.service import record_admin
from app.webhooks.service import emit

log = get_logger("expire_jit_grants")


async def _expire_grants(session) -> int:
    """Deactivate all expired active grants and write audit events. Returns count."""
    now = datetime.now(timezone.utc)

    expired = await session.scalars(
        select(JitGrant).where(
            JitGrant.is_active.is_(True),
            JitGrant.expires_at <= now,
        )
    )
    count = 0
    for grant in expired.all():
        grant.is_active = False
        session.add(grant)

        await record_admin(
            session,
            org_id=str(grant.organization_id),
            actor="system:jit-expirer",
            event_type="access.elevation.expired",
            resource_type="jit_grant",
            resource_id=str(grant.id),
            payload={
                "user_id": str(grant.user_id),
                "granted_by": str(grant.granted_by_user_id),
                "scopes": grant.scopes,
                "justification": grant.justification,
                "ticket_url": grant.ticket_url,
                "expired_at": now.isoformat(),
            },
        )

        await emit(
            session,
            str(grant.organization_id),
            "access.elevation.expired",
            {
                "grant_id": str(grant.id),
                "user_id": str(grant.user_id),
                "scopes": grant.scopes,
            },
        )
        count += 1

    return count


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    t0 = time.perf_counter()
    log.info("jit_expirer.start")

    try:
        async with SessionLocal() as session:
            count = await _expire_grants(session)
            await session.commit()

        elapsed = round(time.perf_counter() - t0, 3)
        log.info("jit_expirer.complete", expired=count, elapsed_s=elapsed)
        return 0
    except Exception as exc:
        log.exception("jit_expirer.error", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
