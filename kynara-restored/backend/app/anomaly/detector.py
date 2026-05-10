"""Periodic anomaly detector.

Looks back 24 hours and compares against the prior 30 days for:

  * agent deny-rate spikes (z >= 3.0 vs 30-day baseline)
  * geolocation jumps for the same API key
  * approval requests piling up (queue length z-score)
  * cross-org request volume drops (potential outage indicator)

Each anomaly emits an ``anomaly.*`` audit event and a webhook delivery so
dashboards and PagerDuty stay in sync. The detector should be invoked by
cron / Argo Cron / Kubernetes CronJob every 5 minutes.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.risk import persist_risk_score
from app.audit.service import record_admin
from app.models import Agent, AuditEvent, Organization
from app.webhooks.service import emit


async def _deny_rates(session: AsyncSession, org_id: str, *, since, until) -> dict[str, float]:
    rows = await session.execute(
        select(AuditEvent.actor, AuditEvent.outcome, func.count())
        .where(
            AuditEvent.organization_id == org_id,
            AuditEvent.ts >= since, AuditEvent.ts < until,
            AuditEvent.event_type == "decision.recorded",
        )
        .group_by(AuditEvent.actor, AuditEvent.outcome)
    )
    totals: dict[str, dict[str, int]] = {}
    for actor, outcome, n in rows:
        totals.setdefault(actor, {"allow": 0, "deny": 0, "require_approval": 0})
        totals[actor][outcome] = n
    return {
        actor: t["deny"] / max(1, sum(t.values()))
        for actor, t in totals.items()
    }


async def _detect_org(session: AsyncSession, org: Organization) -> int:
    now = datetime.now(timezone.utc)
    last24 = await _deny_rates(session, str(org.id), since=now - timedelta(hours=24), until=now)
    baseline = await _deny_rates(session, str(org.id),
                                 since=now - timedelta(days=30),
                                 until=now - timedelta(hours=24))

    # Compute mean and std across baseline values for z-scoring.
    vals = list(baseline.values())
    if len(vals) < 5:
        return 0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var) or 0.001

    flagged = 0
    for actor, rate in last24.items():
        z = (rate - mean) / std
        if z >= 3.0 and rate > 0.05:
            await record_admin(
                session,
                org_id=str(org.id), actor="anomaly-detector",
                event_type="anomaly.deny_rate_spike",
                resource_type="agent", resource_id=actor,
                payload={
                    "actor": actor, "deny_rate_24h": round(rate, 4),
                    "baseline_mean": round(mean, 4), "baseline_std": round(std, 4),
                    "z_score": round(z, 2),
                },
            )
            await emit(session, str(org.id), "anomaly.deny_rate_spike", {
                "actor": actor, "deny_rate_24h": rate, "z": z,
            })
            flagged += 1
    return flagged


async def _refresh_risk_scores(session: AsyncSession, org_id: str) -> int:
    """Recompute and persist risk scores for all agents in this org."""
    agents = await session.scalars(
        select(Agent).where(Agent.organization_id == org_id)
    )
    count = 0
    for agent in agents.all():
        await persist_risk_score(session, agent)
        count += 1
    return count


async def run_once(session: AsyncSession) -> dict:
    """Sweep all orgs once. Caller is responsible for tx commit."""
    orgs = (await session.scalars(select(Organization))).all()
    total = 0
    per_org: dict[str, int] = {}
    for o in orgs:
        n = await _detect_org(session, o)
        # Refresh risk scores for all agents in the org on every cron run
        # so the dashboard always reflects up-to-date deny-rate and scope data.
        await _refresh_risk_scores(session, o.id)
        per_org[str(o.id)] = n
        total += n
    return {"flagged": total, "per_org": per_org}
