"""Audit chain integrity verifier cron entrypoint.

Invoked by the Helm CronJob every 6 hours:
    python -m app.scripts.verify_audit_chain

Every audit event in Kynara is hash-chained: each event's ``entry_hash`` is

    sha256(prev_entry_hash || canonical_json(event_body))

and the next event stores it as its ``prev_hash``. This forms an append-only
Merkle chain per org. Any retroactive tampering — editing a payload, deleting
a row, or inserting a row out of sequence — breaks the chain at the tampered
point and is detected here.

What this job does on each run:
  1. For each org, calls ``audit.service.verify_chain()`` which walks the full
     chain recomputing every hash.
  2. If the chain is intact: logs the tip hash + event count. Clean run.
  3. If the chain is broken:
     - Writes an ``audit.chain_broken`` audit event recording which sequence
       number the break was detected at and what the last good hash was.
     - Fires a ``audit.chain_broken`` webhook so PagerDuty / SIEM is alerted
       immediately.
     - Continues checking remaining orgs (one broken org doesn't abort others).

Exits 0 even when breaks are detected (the job itself succeeded — it's the
downstream alerting that handles the incident). Exits 1 only on unexpected
runtime errors.
"""
from __future__ import annotations

import asyncio
import sys
import time

from sqlalchemy import select

from app.audit.service import record_admin, verify_chain
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import Organization
from app.webhooks.service import emit

log = get_logger("verify_audit_chain")


async def _check_org(session, org: Organization) -> dict:
    org_id = str(org.id)
    result = await verify_chain(session, org_id)

    if result["ok"]:
        log.info(
            "audit_chain.ok",
            org_id=org_id,
            tip=result["tip"][:16] + "…",
            events_checked=result["count"],
        )
    else:
        broken_at = result["broken_at"]
        tip = result["tip"]
        log.error(
            "audit_chain.BROKEN",
            org_id=org_id,
            broken_at_sequence=broken_at,
            last_good_hash=tip[:16] + "…",
        )

        # Write a tamper-evidence audit event. We use record_admin directly
        # rather than the chained _append so a broken chain doesn't prevent
        # the alert from being written.
        try:
            await record_admin(
                session,
                org_id=org_id,
                actor="system:chain-verifier",
                event_type="audit.chain_broken",
                resource_type="audit_chain",
                resource_id=org_id,
                outcome="error",
                payload={
                    "broken_at_sequence": broken_at,
                    "last_good_hash": tip,
                    "events_checked": result["count"],
                },
            )
        except Exception as e:
            log.error("audit_chain.alert_write_failed", org_id=org_id, error=str(e))

        # Fire webhook so downstream SIEM / PagerDuty is notified immediately.
        try:
            await emit(
                session,
                org_id,
                "audit.chain_broken",
                {
                    "org_id": org_id,
                    "broken_at_sequence": broken_at,
                    "last_good_hash": tip,
                },
            )
        except Exception as e:
            log.error("audit_chain.webhook_failed", org_id=org_id, error=str(e))

    return result


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    t0 = time.perf_counter()
    log.info("chain_verifier.start")

    try:
        async with SessionLocal() as session:
            orgs = (await session.scalars(select(Organization))).all()
            total_ok = 0
            total_broken = 0

            for org in orgs:
                result = await _check_org(session, org)
                if result["ok"]:
                    total_ok += 1
                else:
                    total_broken += 1

            await session.commit()

        elapsed = round(time.perf_counter() - t0, 3)
        log.info(
            "chain_verifier.complete",
            orgs_ok=total_ok,
            orgs_broken=total_broken,
            elapsed_s=elapsed,
        )
        # Exit 0 whether or not breaks were found — the job ran successfully.
        # Broken chains are surfaced via audit events and webhooks.
        return 0

    except Exception as exc:
        log.exception("chain_verifier.error", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
