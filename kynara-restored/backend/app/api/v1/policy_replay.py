"""Policy historical replay.

Answers the question: "If I had this policy in place last month, how many of
the decisions actually made would have flipped?"

Implementation: load up to 30 days of decision-recorded audit events with
their full DecisionContext (subject, action, resource, ctx) — re-evaluate
each one against the engine *with the proposed policy spliced in*, and bucket
the deltas: ``would_allow → deny``, ``would_allow → require_approval``, etc.

This is a critical confidence-boost for risky policy changes. The endpoint
caps at 30 days × 100k events to keep replay tractable; for larger windows
the bundle CLI offers an offline replayer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import AuditEvent, Policy
from app.policy.engine import (
    DecisionContext, EngineInput, evaluate, Decision as EngDecision,
)

router = APIRouter(prefix="/policies", tags=["policies"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _admin(p: Principal):
    if p.seat_role not in ("owner", "admin"):
        raise HTTPException(403, "Requires owner or admin role")


class ReplayRequest(BaseModel):
    """Either an existing policy_id (to enable / disable) or a candidate body."""

    candidate_policy: dict[str, Any] | None = None
    enable_policy_id: str | None = None
    disable_policy_id: str | None = None
    window_days: int = 7
    max_events: int = 5000


class ReplayResult(BaseModel):
    window: dict[str, Any]
    counts: dict[str, int]
    flips: dict[str, int]
    samples: list[dict[str, Any]]
    warnings: list[str]


@router.post("/replay", response_model=ReplayResult)
async def replay(
    body: ReplayRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    org_id = uuid.UUID(principal.org_id)
    since = datetime.now(timezone.utc) - timedelta(days=min(body.window_days, 30))

    # Load active policies, then mutate per the request to form the candidate set.
    pols_q = await session.scalars(
        select(Policy).where(
            Policy.organization_id == org_id, Policy.deleted_at.is_(None),
        ).order_by(Policy.priority)
    )
    policies = list(pols_q.all())

    if body.disable_policy_id:
        policies = [p for p in policies if str(p.id) != body.disable_policy_id]
    if body.enable_policy_id:
        for p in policies:
            if str(p.id) == body.enable_policy_id:
                p.is_enabled = True

    if body.candidate_policy:
        # Splice a synthetic Policy-shaped dict in. We use a simple object so
        # the engine sees the same shape it expects.
        class _SyntheticPolicy:
            id = "candidate"
            slug = body.candidate_policy.get("slug") or "candidate"
            display_name = body.candidate_policy.get("display_name") or "candidate"
            effect = body.candidate_policy["effect"]
            priority = int(body.candidate_policy.get("priority", 100))
            actions = body.candidate_policy.get("actions") or []
            resource_types = body.candidate_policy.get("resource_types") or []
            condition = body.candidate_policy.get("condition") or {}
            is_enabled = True
        policies.append(_SyntheticPolicy())  # type: ignore[arg-type]
        policies.sort(key=lambda p: p.priority)

    # Pull historical decision events.
    rows = (await session.scalars(
        select(AuditEvent).where(
            AuditEvent.organization_id == org_id,
            AuditEvent.event_type == "decision.recorded",
            AuditEvent.ts >= since,
        )
        .order_by(AuditEvent.ts.desc())
        .limit(body.max_events)
    )).all()

    counts = {"allow": 0, "deny": 0, "require_approval": 0, "info": 0}
    flips: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    warnings: list[str] = []

    for ev in rows:
        original = ev.outcome
        counts[original] = counts.get(original, 0) + 1

        payload = ev.payload or {}
        try:
            ctx = DecisionContext(
                subject=payload.get("subject", {"type": "unknown", "id": "unknown"}),
                action=payload.get("action") or ev.event_type,
                resource=payload.get("resource", {"type": "unknown"}),
                context=payload.get("context", {}),
            )
            decision: EngDecision = evaluate(EngineInput(ctx=ctx, policies=policies))
        except Exception as e:
            warnings.append(f"replay error on event {ev.sequence}: {e!r}")
            continue

        new_effect = decision.effect
        if new_effect != original:
            key = f"{original} -> {new_effect}"
            flips[key] = flips.get(key, 0) + 1
            if len(samples) < 25:
                samples.append({
                    "sequence": ev.sequence,
                    "ts": ev.ts.isoformat(),
                    "actor": ev.actor,
                    "action": payload.get("action"),
                    "original": original,
                    "replayed": new_effect,
                    "matched_policy": decision.matched_policy_id,
                    "reason": decision.reason,
                })

    return ReplayResult(
        window={"since": since.isoformat(), "events_evaluated": len(rows)},
        counts=counts, flips=flips, samples=samples, warnings=warnings,
    )
