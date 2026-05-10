"""Anomaly detector cron entrypoint.

Invoked by the Helm CronJob every 5 minutes:
    python -m app.scripts.run_anomaly_detector

Exits 0 on success, 1 on failure (so Kubernetes marks the Job as failed
and retries according to the CronJob's restartPolicy).
"""
from __future__ import annotations

import asyncio
import sys
import time

from app.core.logging import configure_logging, get_logger
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.anomaly.detector import run_once

log = get_logger("anomaly_detector_cron")


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    t0 = time.perf_counter()

    log.info("anomaly_detector.start")
    try:
        async with SessionLocal() as session:
            result = await run_once(session)
            await session.commit()
        elapsed = round(time.perf_counter() - t0, 3)
        log.info(
            "anomaly_detector.complete",
            flagged=result["flagged"],
            orgs_scanned=len(result["per_org"]),
            elapsed_s=elapsed,
        )
        return 0
    except Exception as exc:
        log.exception("anomaly_detector.error", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
