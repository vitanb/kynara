"""Agent CRUD + assignments + kill-switch."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.risk import persist_risk_score
from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal, require_scope, require_seat
from app.db.session import SessionLocal
from app.models import Agent, AgentAssignment, Policy, PolicyBinding, Role, RolePermission, User
from app.webhooks.service import emit as emit_webhook

router = APIRouter(prefix="/agents", tags=["agents"])


async def _session():
    async with SessionLocal() as s:
        yield s


class AgentIn(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-_]*$")
    display_name: str
    description: str | None = None
    mode: str = Field(default="human_supervised")
    model: str | None = None
    daily_action_budget: int = 10000


class AgentOut(AgentIn):
    id: str
    is_active: bool
    last_action_at: datetime | None
    created_at: datetime


class AssignmentIn(BaseModel):
    user_id: str
    role_id: str | None = None
    expires_at: datetime | None = None


# ── Agent CRUD ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AgentOut])
async def list_agents(
    principal: Principal = Depends(require_scope("agents.read")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(Agent)
        .where(Agent.organization_id == uuid.UUID(principal.org_id))
        .order_by(Agent.created_at.desc())
    )).all()
    return [AgentOut(
        id=str(r.id), slug=r.slug, display_name=r.display_name,
        description=r.description, mode=r.mode, model=r.model,
        daily_action_budget=r.daily_action_budget,
        is_active=r.is_active, last_action_at=r.last_action_at,
        created_at=r.created_at,
    ) for r in rows]


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin", "developer")),
    session: AsyncSession = Depends(_session),
):
    a = Agent(
        organization_id=uuid.UUID(principal.org_id),
        slug=body.slug, display_name=body.display_name,
        description=body.description, mode=body.mode,
        model=body.model, daily_action_budget=body.daily_action_budget,
    )
    session.add(a)
    try:
        await session.flush()
    except Exception:
        raise HTTPException(status.HTTP_409_CONFLICT, "Agent slug already exists")

    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="agent.created", resource_type="agent", resource_id=str(a.id),
        payload={"slug": a.slug, "mode": a.mode},
        ip_address=request.client.host if request.client else None,
    )
    await persist_risk_score(session, a)
    return AgentOut(id=str(a.id), **body.model_dump(),
                    is_active=a.is_active, last_action_at=None, created_at=a.created_at)


# ── Policies bound to an agent ────────────────────────────────────────────────

@router.get("/{agent_id}/policies")
async def list_agent_policies(
    agent_id: str,
    principal: Principal = Depends(require_scope("agents.read")),
    session: AsyncSession = Depends(_session),
):
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")

    bindings = (await session.scalars(
        select(PolicyBinding).where(
            PolicyBinding.organization_id == uuid.UUID(principal.org_id),
            PolicyBinding.subject_selector.in_([f"agent:{agent_id}", "*"]),
        )
    )).all()
    if not bindings:
        return []

    policy_ids = list({b.policy_id for b in bindings})
    policies = (await session.scalars(select(Policy).where(Policy.id.in_(policy_ids)))).all()

    binding_map: dict = {}
    for b in bindings:
        binding_map.setdefault(b.policy_id, []).append(
            {"id": str(b.id), "subject_selector": b.subject_selector}
        )
    return [
        {
            "id": str(p.id), "slug": p.slug, "display_name": p.display_name,
            "description": p.description, "effect": p.effect, "priority": p.priority,
            "actions": list(p.actions or []), "resource_types": list(p.resource_types or []),
            "is_enabled": p.is_enabled, "bindings": binding_map.get(p.id, []),
        }
        for p in sorted(policies, key=lambda x: x.priority)
    ]


# ── Kill-switch ───────────────────────────────────────────────────────────────

@router.post("/{agent_id}/kill", status_code=204)
async def kill_agent(
    agent_id: str, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")
    a.is_active = False
    await session.commit()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="agent.killed", resource_type="agent", resource_id=str(a.id),
        payload={"slug": a.slug},
        ip_address=request.client.host if request.client else None,
    )


# ── Assignments ───────────────────────────────────────────────────────────────

@router.post("/{agent_id}/assignments", status_code=201)
async def assign_agent(
    agent_id: str, body: AssignmentIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")

    asg = AgentAssignment(
        organization_id=uuid.UUID(principal.org_id),
        agent_id=a.id,
        user_id=uuid.UUID(body.user_id),
        role_id=uuid.UUID(body.role_id) if body.role_id else None,
        expires_at=body.expires_at,
    )
    session.add(asg)
    await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="agent.assigned", resource_type="agent_assignment",
        resource_id=str(asg.id),
        payload={"agent_id": agent_id, "user_id": body.user_id, "role_id": body.role_id},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await emit_webhook(session, org_id=principal.org_id, event_type="agent.permissions_changed", payload={
        "agent_id": agent_id,
        "change": "assignment_added",
        "role_id": body.role_id,
        "user_id": body.user_id,
        "hint": "refresh /api/v1/agents/{agent_id}/access-summary",
    })
    await session.commit()
    return {"assignment_id": str(asg.id), "is_active": asg.is_active}


@router.get("/{agent_id}/assignments")
async def list_assignments(
    agent_id: str,
    principal: Principal = Depends(require_scope("agents.read")),
    session: AsyncSession = Depends(_session),
):
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")

    asgs = (await session.scalars(
        select(AgentAssignment).where(AgentAssignment.agent_id == a.id)
    )).all()

    result = []
    for asg in asgs:
        user = await session.get(User, asg.user_id)
        role = await session.get(Role, asg.role_id) if asg.role_id else None
        result.append({
            "id": str(asg.id),
            "user_id": str(asg.user_id),
            "user_email": user.email if user else None,
            "user_name": user.display_name if user else None,
            "role_id": str(asg.role_id) if asg.role_id else None,
            "role_name": role.display_name if role else None,
            "is_active": asg.is_active,
            "expires_at": asg.expires_at.isoformat() if asg.expires_at else None,
        })
    return result


@router.delete("/{agent_id}/assignments/{assignment_id}", status_code=204)
async def remove_assignment(
    agent_id: str, assignment_id: str, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    asg = await session.get(AgentAssignment, uuid.UUID(assignment_id))
    if not asg or asg.agent_id != uuid.UUID(agent_id):
        raise HTTPException(404, "Assignment not found")
    org_id = str(asg.organization_id)
    role_id = str(asg.role_id) if asg.role_id else None
    await session.delete(asg)
    await session.commit()
    await emit_webhook(session, org_id=org_id, event_type="agent.permissions_changed", payload={
        "agent_id": agent_id,
        "change": "assignment_removed",
        "role_id": role_id,
        "hint": "refresh /api/v1/agents/{agent_id}/access-summary",
    })
    await session.commit()


# ── Roles alias (used by AgentDetail assignment form) ─────────────────────────

@router.get("/roles")
async def list_roles_alias(
    principal: Principal = Depends(require_scope("agents.read")),
    session: AsyncSession = Depends(_session),
):
    """Alias: returns org roles so the assignment form can populate a dropdown."""
    rows = (await session.scalars(
        select(Role)
        .where(Role.organization_id == uuid.UUID(principal.org_id))
        .order_by(Role.display_name)
    )).all()
    result = []
    for r in rows:
        scopes = (await session.scalars(
            select(RolePermission.scope).where(RolePermission.role_id == r.id)
        )).all()
        result.append({
            "id": str(r.id),
            "slug": r.slug,
            "display_name": r.display_name,
            "description": r.description,
            "scopes": sorted(scopes),
        })
    return result


# -- Access summary (agent init export) ------------------------------------------

@router.get("/{agent_id}/access-summary")
async def get_access_summary(
    agent_id: str,
    principal: Principal = Depends(require_scope("agents.read")),
    session: AsyncSession = Depends(_session),
):
    """Return the complete, denormalised access picture for a single agent.

    Designed for agents to call once at initialisation and cache locally.
    Response includes: agent metadata, every active role assignment with its
    full scope list, and every policy that applies to this agent (either by
    direct binding or via a wildcard binding).  A sha256 checksum covers
    the permission-relevant fields so the caller can detect changes without
    re-parsing the full body.
    """
    import hashlib, json

    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")

    asgs = (await session.scalars(
        select(AgentAssignment).where(
            AgentAssignment.agent_id == a.id,
            AgentAssignment.is_active.is_(True),
        )
    )).all()

    assignments_out = []
    all_scopes: set[str] = set()
    for asg in asgs:
        role = await session.get(Role, asg.role_id) if asg.role_id else None
        scopes: list[str] = []
        if role:
            scopes = sorted((await session.scalars(
                select(RolePermission.scope).where(RolePermission.role_id == role.id)
            )).all())
            all_scopes.update(scopes)
        assignments_out.append({
            "assignment_id": str(asg.id),
            "user_id": str(asg.user_id),
            "role_id": str(asg.role_id) if asg.role_id else None,
            "role_slug": role.slug if role else None,
            "role_display_name": role.display_name if role else None,
            "granted_scopes": scopes,
            "expires_at": asg.expires_at.isoformat() if asg.expires_at else None,
        })

    bindings = (await session.scalars(
        select(PolicyBinding).where(
            PolicyBinding.organization_id == uuid.UUID(principal.org_id),
            PolicyBinding.subject_selector.in_([f"agent:{agent_id}", "*"]),
        )
    )).all()
    policy_ids = list({b.policy_id for b in bindings})
    policies_rows = (await session.scalars(
        select(Policy).where(
            Policy.id.in_(policy_ids),
            Policy.deleted_at.is_(None),
            Policy.is_enabled.is_(True),
        ).order_by(Policy.priority)
    )).all() if policy_ids else []

    policies_out = [
        {
            "id": str(p.id),
            "slug": p.slug,
            "display_name": p.display_name,
            "effect": p.effect,
            "priority": p.priority,
            "actions": list(p.actions or []),
            "resource_types": list(p.resource_types or []),
            "condition": p.condition,
        }
        for p in policies_rows
    ]

    perm_body = {
        "agent_id": agent_id,
        "is_active": a.is_active,
        "mode": a.mode,
        "assignments": sorted(
            [{"role_id": x["role_id"], "scopes": x["granted_scopes"]} for x in assignments_out],
            key=lambda x: x["role_id"] or "",
        ),
        "policy_ids": sorted(str(p.id) for p in policies_rows),
    }
    checksum = "sha256:" + hashlib.sha256(
        json.dumps(perm_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "agent_id": agent_id,
        "slug": a.slug,
        "display_name": a.display_name,
        "mode": a.mode,
        "is_active": a.is_active,
        "daily_action_budget": a.daily_action_budget,
        "assignments": assignments_out,
        "granted_scopes": sorted(all_scopes),
        "applicable_policies": policies_out,
        "checksum": checksum,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Edit agent ────────────────────────────────────────────────────────────────

class AgentUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    mode: str | None = None
    model: str | None = None
    daily_action_budget: int | None = None


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str, body: AgentUpdate, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin", "developer")),
    session: AsyncSession = Depends(_session),
):
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")

    changed: dict = {}
    for field, value in body.model_dump(exclude_none=True).items():
        if getattr(a, field) != value:
            setattr(a, field, value)
            changed[field] = value

    if changed:
        await session.commit()
        await record_admin(
            session, org_id=principal.org_id,
            actor=f"user:{principal.user_id}" if principal.user_id else "system",
            event_type="agent.updated", resource_type="agent", resource_id=str(a.id),
            payload={"changes": changed},
            ip_address=request.client.host if request.client else None,
        )
        await persist_risk_score(session, a)

    return AgentOut(
        id=str(a.id), slug=a.slug, display_name=a.display_name,
        description=a.description, mode=a.mode, model=a.model,
        daily_action_budget=a.daily_action_budget,
        is_active=a.is_active, last_action_at=a.last_action_at,
        created_at=a.created_at,
    )


# ── Risk score ───────────────────────────────────────────────────────────────

class RiskOut(BaseModel):
    agent_id: str
    risk_score: float | None
    risk_class: str
    risk_factors: dict
    scored_at: str | None  # last updated_at timestamp


@router.get("/{agent_id}/risk", response_model=RiskOut)
async def get_agent_risk(
    agent_id: str,
    principal: Principal = Depends(require_scope("agents.read")),
    session: AsyncSession = Depends(_session),
):
    """Return the current computed risk score, contributing factors, and risk class."""
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")

    return RiskOut(
        agent_id=str(a.id),
        risk_score=a.risk_score,
        risk_class=a.risk_class,
        risk_factors=a.risk_factors or {},
        scored_at=a.updated_at.isoformat() if hasattr(a, "updated_at") and a.updated_at else None,
    )


# ── Reactivate ────────────────────────────────────────────────────────────────

@router.post("/{agent_id}/reactivate", status_code=204)
async def reactivate_agent(
    agent_id: str, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    a = await session.get(Agent, uuid.UUID(agent_id))
    if not a or a.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Agent not found")
    if a.is_active:
        return  # already active — no-op
    a.is_active = True
    await session.commit()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="agent.reactivated", resource_type="agent", resource_id=str(a.id),
        payload={"slug": a.slug},
        ip_address=request.client.host if request.client else None,
    )
