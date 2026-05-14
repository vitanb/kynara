"""Decision service — loads policies, resolves subject scopes, invokes the engine,
caches recent decisions (Redis), and writes the audit event.

All ``/v1/decisions/check`` traffic goes through this module.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_decision
from app.core.config import get_settings
from app.models import ApprovalRequest
from app.core.logging import get_logger
from app.core.telemetry import decisions_total, decision_latency, get_tracer
from app.models import Agent, AgentAssignment, Policy, PolicyBinding, Role, RolePermission
from app.models.jit_grant import JitGrant
from app.policy.engine import (
    Decision,
    DecisionContext,
    EngineInput,
    _PolicyRow,
    evaluate,
)

log = get_logger("policy.service")
tracer = get_tracer()
_redis: redis_async.Redis | None = None


async def _r() -> redis_async.Redis:
    global _redis
    if _redis is None:
        _redis = redis_async.from_url(str(get_settings().redis_url), decode_responses=True)
    return _redis


def _cache_key(org_id: str, subject_id: str, action: str, resource_id: str) -> str:
    return f"dec:{org_id}:{subject_id}:{action}:{resource_id}"


async def decide(
    session: AsyncSession,
    *,
    org_id: str,
    subject_type: str,  # "agent" | "user" | "api_key"
    subject_id: str,
    on_behalf_of_user_id: str | None,
    action: str,
    resource: dict[str, Any],
    context: dict[str, Any],
) -> Decision:
    settings = get_settings()
    t0 = time.perf_counter()

    ck = _cache_key(org_id, subject_id, action, resource.get("id", ""))
    try:
        cache = await _r()
        cached = await cache.get(ck)
        if cached:
            d = Decision(**json.loads(cached))
            _record_metrics(org_id, d.effect, time.perf_counter() - t0, cached=True)
            return d
    except Exception as _cache_err:
        log.warning("policy.cache_unavailable", err=str(_cache_err))
        cache = None

    with tracer.start_as_current_span("policy.decide") as span:
        span.set_attribute("kynara.action", action)
        span.set_attribute("kynara.subject.type", subject_type)
        span.set_attribute("kynara.subject.id", subject_id)

        try:
            # --- Hard gates ------------------------------------------------
            if subject_type == "agent":
                agent = await session.get(Agent, uuid.UUID(subject_id))
                if not agent or not agent.is_active:
                    return await _emit_decision(
                        session, org_id, subject_type, subject_id, on_behalf_of_user_id,
                        action, resource, context,
                        Decision(effect="deny", reason="agent disabled"),
                        t0,
                    )
                if agent.organization_id != uuid.UUID(org_id):
                    return await _emit_decision(
                        session, org_id, subject_type, subject_id, on_behalf_of_user_id,
                        action, resource, context,
                        Decision(effect="deny", reason="agent/org mismatch"),
                        t0,
                    )

            # --- Resolve role grants ---------------------------------------
            granted = await _resolve_granted_scopes(
                session, org_id, subject_type, subject_id, on_behalf_of_user_id
            )

            # --- Fetch bound policies --------------------------------------
            selectors = [
                f"{subject_type}:{subject_id}",
                "*",
            ]
            if on_behalf_of_user_id:
                selectors.append(f"user:{on_behalf_of_user_id}")

            policies = await _load_bound_policies(session, org_id, selectors)

            ctx = DecisionContext(
                subject={
                    "id": subject_id,
                    "type": subject_type,
                    "attrs": {
                        "scopes": granted,
                        "on_behalf_of": on_behalf_of_user_id,
                    },
                },
                action=action,
                resource=resource,
                context=context,
            )
            decision = evaluate(
                EngineInput(policies=policies, granted_scopes=granted, default_effect="deny"),
                ctx,
            )
        except Exception as e:
            log.exception("policy_engine_error", err=str(e))
            # fail-closed by default
            decision = Decision(
                effect="deny" if settings.deny_on_policy_error else "allow",
                reason=f"engine error: {e}",
            )

    # Cache only *non-approval* decisions — approvals must always re-check.
    if decision.effect != "require_approval" and cache is not None:
        try:
            await cache.setex(ck, settings.decision_cache_ttl_seconds, json.dumps(asdict(decision)))
        except Exception as _cache_err:
            log.warning("policy.cache_write_failed", err=str(_cache_err))

    return await _emit_decision(
        session, org_id, subject_type, subject_id, on_behalf_of_user_id,
        action, resource, context, decision, t0,
    )


async def _emit_decision(
    session, org_id, subject_type, subject_id, on_behalf_of_user_id,
    action, resource, context, decision, t0,
) -> Decision:
    await record_decision(
        session,
        org_id=org_id,
        actor=f"{subject_type}:{subject_id}",
        on_behalf_of=f"user:{on_behalf_of_user_id}" if on_behalf_of_user_id else None,
        action=action,
        resource_type=resource.get("type"),
        resource_id=resource.get("id"),
        decision=decision,
        request_id=context.get("request_id"),
        ip_address=context.get("ip"),
    )

    # When approval is required, create a persistent approval request record.
    if decision.effect == "require_approval":
        from datetime import timedelta
        approval = ApprovalRequest(
            organization_id=uuid.UUID(org_id),
            subject_type=subject_type,
            subject_id=subject_id,
            on_behalf_of_user_id=on_behalf_of_user_id,
            action=action,
            resource_type=resource.get("type"),
            resource_id=resource.get("id"),
            resource_attrs=resource.get("attrs") or {},
            context={k: v for k, v in context.items()
                     if k not in ("request_id", "ip")},
            matched_policy_id=decision.matched_policy_id,
            status="pending",
            expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=24),
        )
        session.add(approval)
        await session.flush()
        # Attach the approval_id to the decision so the caller can surface it.
        decision.approval_id = str(approval.id)  # type: ignore[attr-defined]

        # Fire an email alert if the matched policy has an approval_email set.
        if decision.matched_policy_id:
            try:
                from app.models import Policy as _Policy
                from app.core.email import send_email, approval_request_email_content
                policy_row = await session.get(_Policy, uuid.UUID(decision.matched_policy_id))
                if policy_row and policy_row.approval_email:
                    html, plain = approval_request_email_content(
                        agent_id=subject_id,
                        action=action,
                        resource_type=resource.get("type"),
                        approval_id=str(approval.id),
                        app_url=settings.app_url,
                    )
                    await send_email(
                        to=policy_row.approval_email,
                        subject=f"[Kynara] Approval required: {action}",
                        html_body=html,
                        text_body=plain,
                    )
                    log.info(
                        "approval_email_sent",
                        approval_id=str(approval.id),
                        to=policy_row.approval_email,
                    )
            except Exception as _email_err:
                # Non-fatal — the approval request is already persisted.
                log.warning("approval_email_send_failed", err=str(_email_err))

    _record_metrics(org_id, decision.effect, time.perf_counter() - t0)
    return decision


def _record_metrics(org_id: str, effect: str, seconds: float, cached: bool = False) -> None:
    decisions_total.labels(org_id=org_id, effect=effect).inc()
    decision_latency.observe(seconds)


async def _resolve_granted_scopes(
    session: AsyncSession,
    org_id: str,
    subject_type: str,
    subject_id: str,
    on_behalf_of_user_id: str | None,
) -> list[str]:
    """Resolve the effective scope set for the requesting subject.

    Three cases:
    1. user / api_key  →  role scopes ∪ active JIT grants for that user.
    2. agent + on_behalf_of_user_id  →  *intersection* of the assignment's role
       grants and the delegating user's grants (non-escalation safety property).
    3. agent without on_behalf_of_user_id (autonomous mode)  →  union of all
       active assignment role scopes for that agent (no delegating user required).
    """
    if subject_type != "agent":
        # user or api_key
        return await _scopes_for_user(session, org_id, subject_id)

    if on_behalf_of_user_id:
        # Agent delegated by a specific user — intersection enforces non-escalation.
        assignment = await session.scalar(
            select(AgentAssignment).where(
                AgentAssignment.agent_id == uuid.UUID(subject_id),
                AgentAssignment.user_id == uuid.UUID(on_behalf_of_user_id),
                AgentAssignment.is_active.is_(True),
            )
        )
        if not assignment:
            return []

        agent_scopes: set[str] = set()
        if assignment.role_id:
            rp = await session.scalars(
                select(RolePermission.scope).where(RolePermission.role_id == assignment.role_id)
            )
            agent_scopes = set(rp.all())

        user_scopes = set(await _scopes_for_user(session, org_id, on_behalf_of_user_id))
        return sorted(agent_scopes & user_scopes) if agent_scopes else []

    # Autonomous agent — derive scopes from ALL its active role assignments.
    return await _scopes_for_agent(session, org_id, subject_id)


async def _active_jit_scopes(session: AsyncSession, org_id: str, user_id: str) -> set[str]:
    """Return the union of all scopes from active, non-expired JIT grants for this user."""
    now = datetime.now(tz=timezone.utc)
    grants = await session.scalars(
        select(JitGrant).where(
            JitGrant.organization_id == uuid.UUID(org_id),
            JitGrant.user_id == uuid.UUID(user_id),
            JitGrant.is_active.is_(True),
            JitGrant.expires_at > now,
        )
    )
    scopes: set[str] = set()
    for g in grants.all():
        scopes.update(g.scopes or [])
    return scopes


async def _scopes_for_user(session: AsyncSession, org_id: str, user_id: str) -> list[str]:
    """Return the full effective scope set for a user: role-based scopes ∪ active JIT grants."""
    from app.models import OrgMembership
    mem = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.user_id == uuid.UUID(user_id),
            OrgMembership.organization_id == uuid.UUID(org_id),
        )
    )
    if not mem:
        return []

    # Role-based scopes
    if mem.seat_role in ("owner", "admin"):
        base_scopes: set[str] = {"*"}
    else:
        base_scopes = {"self.read", "self.update"}

    # Union in any active JIT elevations
    jit_scopes = await _active_jit_scopes(session, org_id, user_id)
    return sorted(base_scopes | jit_scopes)


async def _scopes_for_agent(session: AsyncSession, org_id: str, agent_id: str) -> list[str]:
    """Return the union of role scopes across all active assignments for an autonomous agent.

    Autonomous agents are not delegated by a specific user, so we union the scopes
    from every active AgentAssignment role.  If no assignments or roles exist the
    agent gets no scopes (deny-by-default).
    """
    assignments = (await session.scalars(
        select(AgentAssignment).where(
            AgentAssignment.agent_id == uuid.UUID(agent_id),
            AgentAssignment.organization_id == uuid.UUID(org_id),
            AgentAssignment.is_active.is_(True),
        )
    )).all()

    scopes: set[str] = set()
    for assignment in assignments:
        if assignment.role_id:
            rp = await session.scalars(
                select(RolePermission.scope).where(RolePermission.role_id == assignment.role_id)
            )
            scopes.update(rp.all())

    return sorted(scopes)


async def _load_bound_policies(
    session: AsyncSession, org_id: str, selectors: list[str]
) -> list[_PolicyRow]:
    rows = (
        await session.execute(
            select(Policy)
            .join(PolicyBinding, PolicyBinding.policy_id == Policy.id)
            .where(
                Policy.organization_id == uuid.UUID(org_id),
                Policy.is_enabled.is_(True),
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
