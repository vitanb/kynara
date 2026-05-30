"""Agent risk score update cron — runs daily at 03:00 UTC.

Invoked by the Helm CronJob:
    python -m app.scripts.update_risk_scores

For every active agent in every organisation the script:

1. Loads up to 30 days of ``decision.recorded`` audit events for that agent.
2. Computes a composite risk score 0–100:

   - deny_rate        (weight 40):  denied / total
   - approval_rate    (weight 30):  require_approval / total
   - anomaly_flag_rate(weight 30):  events with "anomaly" in event_type / total

3. Persists ``agent.risk_score`` and ``agent.risk_factors``.
4. Upgrades ``agent.risk_class`` to "high" (score > 75) or "critical" (> 90).
   Agents below 75 are left at their current class (administrators set the
   baseline; the scorer only escalates).

Exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import Agent, AuditEvent, Organization

log = get_logger("update_risk_scores")

# Scoring weights — must sum to 100
_W_DENY = 40
_W_APPROVAL = 30
_W_ANOMALY = 30

_WINDOW_DAYS = 30
_HIGH_THRESHOLD = 75.0
_CRITICAL_THRESHOLD = 90.0


def _compute_score(
    total: int,
    denied: int,
    approval_required: int,
    anomaly_flagged: int,
) -> tuple[float, dict]:
    """Return (score_0_to_100, factors_dict)."""
    if total == 0:
        return 0.0, {"total_decisions": 0}

    deny_rate = denied / total
    approval_rate = approval_required / total
    anomaly_rate = anomaly_flagged / total

    score = (
        deny_rate * _W_DENY
        + approval_rate * _W_APPROVAL
        + anomaly_rate * _W_ANOMALY
    )
    score = round(min(score * 100, 100.0), 2)

    factors = {
        "total_decisions": total,
        "denied": denied,
        "approval_required": approval_required,
        "anomaly_flagged": anomaly_flagged,
        "deny_rate": round(deny_rate, 4),
        "approval_rate": round(approval_rate, 4),
        "anomaly_flag_rate": round(anomaly_rate, 4),
        "window_days": _WINDOW_DAYS,
    }
    return score, factors


async def _update_org_agents(session, org_id: str) -> int:
    """Update risk scores for all active agents in one org. Returns count updated."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)

    agents = (await session.scalars(
        select(Agent).where(
            Agent.organization_id == org_id,
            Agent.is_active.is_(True),
        )
    )).all()

    updated = 0
    for agent in agents:
        agent_actor_prefix = f"agent:{agent.id}"

        # Count total decision events for this agent
        total = (await session.scalar(
            select(func.count()).where(
                AuditEvent.organization_id == org_id,
                AuditEvent.event_type == "decision.recorded",
                AuditEvent.actor == agent_actor_prefix,
                AuditEvent.ts >= cutoff,
            )
        )) or 0

        denied = (await session.scalar(
            select(func.count()).where(
                AuditEvent.organization_id == org_id,
                AuditEvent.event_type == "decision.recorded",
                AuditEvent.actor == agent_actor_prefix,
                AuditEvent.outcome == "deny",
                AuditEvent.ts >= cutoff,
            )
        )) or 0

        approval_required = (await session.scalar(
            select(func.count()).where(
                AuditEvent.organization_id == org_id,
                AuditEvent.event_type == "decision.recorded",
                AuditEvent.actor == agent_actor_prefix,
                AuditEvent.outcome == "require_approval",
                AuditEvent.ts >= cutoff,
            )
        )) or 0

        # Anomaly events — any audit event whose type contains "anomaly"
        anomaly_flagged = (await session.scalar(
            select(func.count()).where(
                AuditEvent.organization_id == org_id,
                AuditEvent.actor == agent_actor_prefix,
                AuditEvent.event_type.contains("anomaly"),
                AuditEvent.ts >= cutoff,
            )
        )) or 0

        score, factors = _compute_score(total, denied, approval_required, anomaly_flagged)

        agent.risk_score = score
        agent.risk_factors = factors

        # Only escalate risk_class — never auto-downgrade
        if score > _CRITICAL_THRESHOLD:
            agent.risk_class = "critical"
        elif score > _HIGH_THRESHOLD:
            agent.risk_class = "high"

        session.add(agent)
        updated += 1

        log.info(
            "risk_score.updated",
            agent_id=str(agent.id),
            org_id=str(org_id),
            score=score,
            risk_class=agent.risk_class,
            total_decisions=total,
        )

    return updated


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    t0 = time.perf_counter()
    log.info("risk_scorer.start")

    total_updated = 0
    try:
        async with SessionLocal() as session:
            orgs = (await session.scalars(select(Organization))).all()
            for org in orgs:
                count = await _update_org_agents(session, org.id)
                total_updated += count

            await session.commit()

        elapsed = round(time.perf_counter() - t0, 3)
        log.info(
            "risk_scorer.complete",
            agents_updated=total_updated,
            elapsed_s=elapsed,
        )
        return 0
    except Exception as exc:
        log.exception("risk_scorer.error", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
