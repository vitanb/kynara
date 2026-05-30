"""Policy simulation and historical replay endpoints.

POST /policies/simulate  — dry-run a single hypothetical request through the
    current policy engine without writing any audit event or usage record.
    Returns effect, matched policy, and reason.

POST /policies/replay  — re-evaluate all policy.decision audit events from a
    given time window against the *current* policy set and report which
    decisions would flip (allow→deny, deny→allow, etc.).

Both require the ``policy.read`` scope.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, require_scope
from app.db.session import SessionLocal
from app.models import Agent, AuditEvent, Policy, PolicyBinding, RolePermission, AgentAssignment
from app.models.jit_grant import JitGrant
from app.policy.engine import (
    Decision,
    DecisionContext,
    EngineInput,
    _PolicyRow,
    evaluate,
)

router = APIRouter(prefix="/policies", tags=["policies"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ── request / response schemas ────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    agent_id: str
    action: str
    resource: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class SimulateResult(BaseModel):
    effect: str
    matched_policy_id: str | None
    matched_policy_slug: str | None
    reason: str | None


class ReplayRequest(BaseModel):
    since: datetime
    until: datetime | None = None
    max_events: int = Field(default=5000, ge=1, le=100_000)


class ReplayDiffItem(BaseModel):
    audit_sequence: int
    ts: str
    actor: str
    action: str | None
    original_effect: str
    replayed_effect: str
    matched_policy_id: str | None
    reason: str | None


class ReplayResult(BaseModel):
    window: dict[str, Any]
    events_evaluated: int
    summary: dict[str, int]          # flip_key → count, e.g. "allow->deny": 3
    unchanged: int
    diffs: list[ReplayDiffItem]       # capped at 100 samples


# ── helpers ───────────────────────────────────────────────────────────────────

async def _load_policies_for_agent(
    session: AsyncSession,
    org_id: uuid.UUID,
    agent_id: str,
) -> list[_PolicyRow]:
    """Return the _PolicyRow list for an agent using direct + wildcard bindings."""
    selectors = [f"agent:{agent_id}", "*"]
    rows = (
        await session.execute(
            select(Policy)
            .join(PolicyBinding, PolicyBinding.policy_id == Policy.id)
            .where(
                Policy.organization_id == org_id,
                Policy.is_enabled.is_(True),
                Policy.deleted_at.is_(None),
                PolicyBinding.subject_selector.in_(selectors),
            )
            .order_by(Policy.priority.asc())
        )
    ).scalars().all()

    return [
        _PolicyRow(
            id=str(p.id),
            priority=p.priority,
            effect=p.effect,
            actions=list(p.actions or []),
            resource_types=list(p.resource_types or []),
            condition=p.condition or {},
            is_enabled=p.is_enabled,
        )
        for p in rows
    ]


async def _granted_scopes_for_agent(
    session: AsyncSession,
    org_id: uuid.UUID,
    agent_id: str,
) -> list[str]:
    """Union of role scopes across all active assignments (autonomous mode)."""
    assignments = (await session.scalars(
        select(AgentAssignment).where(
            AgentAssignment.agent_id == uuid.UUID(agent_id),
            AgentAssignment.organization_id == org_id,
            AgentAssignment.is_active.is_(True),
        )
    )).all()

    scopes: set[str] = set()
    for asg in assignments:
        if asg.role_id:
            rp = await session.scalars(
                select(RolePermission.scope).where(RolePermission.role_id == asg.role_id)
            )
            scopes.update(rp.all())
    return sorted(scopes)


async def _slug_for_policy_id(
    session: AsyncSession, policy_id: str | None
) -> str | None:
    if not policy_id:
        return None
    try:
        p = await session.get(Policy, uuid.UUID(policy_id))
        return p.slug if p else None
    except Exception:
        return None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/simulate", response_model=SimulateResult)
async def simulate(
    body: SimulateRequest,
    principal: Principal = Depends(require_scope("policy.read")),
    session: AsyncSession = Depends(_session),
):
    """Dry-run a single request through the current policy engine.

    No audit event is written and no usage record is incremented — this is a
    pure read-path simulation for debugging and policy authoring.
    """
    org_id = uuid.UUID(principal.org_id)

    # Validate agent belongs to the org.
    try:
        agent = await session.get(Agent, uuid.UUID(body.agent_id))
    except ValueError:
        raise HTTPException(400, "Invalid agent_id")
    if not agent or agent.organization_id != org_id:
        raise HTTPException(404, "Agent not found")

    if not agent.is_active:
        return SimulateResult(
            effect="deny",
            matched_policy_id=None,
            matched_policy_slug=None,
            reason="agent disabled",
        )

    granted = await _granted_scopes_for_agent(session, org_id, body.agent_id)
    policies = await _load_policies_for_agent(session, org_id, body.agent_id)

    ctx = DecisionContext(
        subject={
            "id": body.agent_id,
            "type": "agent",
            "attrs": {"scopes": granted},
        },
        action=body.action,
        resource=body.resource,
        context=body.context,
    )

    try:
        decision: Decision = evaluate(
            EngineInput(policies=policies, granted_scopes=granted, default_effect="deny"),
            ctx,
        )
    except Exception as exc:
        raise HTTPException(500, f"Policy engine error: {exc}")

    slug = await _slug_for_policy_id(session, decision.matched_policy_id)
    return SimulateResult(
        effect=decision.effect,
        matched_policy_id=decision.matched_policy_id,
        matched_policy_slug=slug,
        reason=decision.reason,
    )


@router.post("/simulate/replay", response_model=ReplayResult)
async def replay_window(
    body: ReplayRequest,
    principal: Principal = Depends(require_scope("policy.read")),
    session: AsyncSession = Depends(_session),
):
    """Re-evaluate audit events from a time window against the current policy set.

    Loads up to ``max_events`` ``policy.decision`` audit events between
    ``since`` and ``until`` (defaults to now), re-runs each through the *live*
    policy engine, and reports which decisions would change.

    The diff list is capped at 100 representative samples; the summary counts
    are always accurate.
    """
    org_id = uuid.UUID(principal.org_id)
    since = body.since
    until = body.until or datetime.now(timezone.utc)

    if until <= since:
        raise HTTPException(400, "until must be after since")
    if (until - since) > timedelta(days=30):
        raise HTTPException(400, "Window may not exceed 30 days")

    # Ensure datetimes are tz-aware
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)

    # Load historical decision events
    events = (await session.scalars(
        select(AuditEvent).where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "decision.recorded",
            AuditEvent.ts >= since,
            AuditEvent.ts <= until,
        )
        .order_by(AuditEvent.ts.asc())
        .limit(body.max_events)
    )).all()

    # Pre-load all enabled policies for the org (not agent-filtered — we
    # replay using the full policy set and whatever selectors the event recorded)
    all_policies = (await session.scalars(
        select(Policy).where(
            Policy.organization_id == org_id,
            Policy.is_enabled.is_(True),
            Policy.deleted_at.is_(None),
        ).order_by(Policy.priority.asc())
    )).all()

    policy_rows = [
        _PolicyRow(
            id=str(p.id),
            priority=p.priority,
            effect=p.effect,
            actions=list(p.actions or []),
            resource_types=list(p.resource_types or []),
            condition=p.condition or {},
            is_enabled=p.is_enabled,
        )
        for p in all_policies
    ]

    summary: dict[str, int] = {}
    unchanged = 0
    diffs: list[ReplayDiffItem] = []

    for ev in events:
        original = ev.outcome or "unknown"
        payload = ev.payload or {}

        try:
            ctx = DecisionContext(
                subject=payload.get("subject", {"type": "unknown", "id": "unknown"}),
                action=payload.get("action") or "",
                resource=payload.get("resource", {"type": "unknown"}),
                context=payload.get("context", {}),
            )
            granted = ctx.subject.get("attrs", {}).get("scopes", [])
            decision: Decision = evaluate(
                EngineInput(policies=policy_rows, granted_scopes=granted, default_effect="deny"),
                ctx,
            )
            replayed = decision.effect
        except Exception:
            # Skip events that cannot be replayed
            continue

        if replayed != original:
            flip_key = f"{original}->{replayed}"
            summary[flip_key] = summary.get(flip_key, 0) + 1
            if len(diffs) < 100:
                diffs.append(ReplayDiffItem(
                    audit_sequence=ev.sequence,
                    ts=ev.ts.isoformat(),
                    actor=ev.actor or "",
                    action=payload.get("action"),
                    original_effect=original,
                    replayed_effect=replayed,
                    matched_policy_id=decision.matched_policy_id,
                    reason=decision.reason,
                ))
        else:
            unchanged += 1

    return ReplayResult(
        window={
            "since": since.isoformat(),
            "until": until.isoformat(),
        },
        events_evaluated=len(events),
        summary=summary,
        unchanged=unchanged,
        diffs=diffs,
    )
