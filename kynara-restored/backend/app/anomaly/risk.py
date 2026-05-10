"""Per-agent risk scoring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, AuditEvent, AgentAssignment, RolePermission

# Weights are tunable per-org via configuration. Defaults sum to 100.
W_TOOL_RISK        = 25
W_DENY_RATE        = 25
W_AUTONOMY         = 20
W_SENSITIVE_SCOPES = 15
W_AGE              = 15

RISK_TO_SCORE = {"low": 10, "medium": 40, "high": 70, "critical": 100}

_SENSITIVE_PREFIXES = ("payments.", "secrets.", "admin.", "billing.", "iam.", "kms.")


async def score_agent(session: AsyncSession, agent: Agent) -> dict[str, Any]:
    """Compute and return a risk dict: {"score": 0..100, "factors": {...}}.

    Higher score = riskier. Call persist_risk_score() to write results back
    to the agent row.
    """
    factors: dict[str, float] = {}

    # 1. Inherent risk from the agent's own risk_class.
    base_risk = RISK_TO_SCORE.get(getattr(agent, "risk_class", "medium"), 50)
    factors["base_risk"] = base_risk

    # 2. Mode amplifies it: autonomous > human_supervised > read_only.
    autonomy_mult = {"autonomous": 1.0, "human_supervised": 0.6, "read_only": 0.3}.get(
        getattr(agent, "mode", "human_supervised"), 0.6,
    )
    factors["autonomy_mult"] = autonomy_mult

    # 3. Deny rate over the last 7 days.
    since = datetime.now(timezone.utc) - timedelta(days=7)
    actor_key = f"agent:{agent.slug}"
    decisions = await session.scalar(
        select(func.count()).where(
            AuditEvent.actor == actor_key,
            AuditEvent.ts >= since,
            AuditEvent.event_type == "decision.recorded",
        )
    ) or 0
    denies = await session.scalar(
        select(func.count()).where(
            AuditEvent.actor == actor_key,
            AuditEvent.ts >= since,
            AuditEvent.outcome == "deny",
        )
    ) or 0
    deny_rate = (denies / decisions) if decisions else 0
    factors["deny_rate_7d"] = round(deny_rate, 4)

    # 4. Age factor: brand-new agents are riskier (less observed behaviour).
    age_days = (datetime.now(timezone.utc) - agent.created_at).days if agent.created_at else 0
    age_factor = 1.0 if age_days < 7 else (0.6 if age_days < 30 else 0.2)
    factors["age_factor"] = age_factor

    # 5. Sensitive-scope ownership: fraction of assigned scopes that match
    #    sensitive prefixes (payments, secrets, admin, billing, iam, kms).
    assignments = await session.scalars(
        select(AgentAssignment).where(
            AgentAssignment.agent_id == agent.id,
            AgentAssignment.is_active.is_(True),
        )
    )
    all_scopes: list[str] = []
    for assignment in assignments.all():
        if assignment.role_id:
            role_scopes = await session.scalars(
                select(RolePermission.scope).where(
                    RolePermission.role_id == assignment.role_id
                )
            )
            all_scopes.extend(role_scopes.all())

    if all_scopes:
        sensitive_count = sum(
            1 for s in all_scopes
            if any(s.startswith(p) for p in _SENSITIVE_PREFIXES) or s == "*"
        )
        sensitive_factor = min(1.0, sensitive_count / len(all_scopes))
    else:
        sensitive_factor = 0.0
    factors["sensitive_factor"] = round(sensitive_factor, 4)
    factors["scope_count"] = len(all_scopes)

    score = (
        W_TOOL_RISK        * (base_risk / 100) +
        W_AUTONOMY         * autonomy_mult +
        W_DENY_RATE        * min(1.0, deny_rate * 4) +
        W_SENSITIVE_SCOPES * sensitive_factor +
        W_AGE              * age_factor
    )
    score = max(0.0, min(100.0, score))
    return {"score": round(score, 1), "factors": factors}


async def persist_risk_score(session: AsyncSession, agent: Agent) -> float:
    """Compute the risk score for *agent*, write it back to the row, and return the score.

    Callers are responsible for committing the session.
    """
    result = await score_agent(session, agent)
    agent.risk_score = result["score"]      # type: ignore[attr-defined]
    agent.risk_factors = result["factors"]  # type: ignore[attr-defined]
    session.add(agent)
    return result["score"]
