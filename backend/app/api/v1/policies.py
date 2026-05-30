"""Policy CRUD + binding management + versioning/rollback."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal, require_scope, require_seat
from app.db.session import SessionLocal
from app.models import Policy, PolicyBinding, PolicyVersion

router = APIRouter(prefix="/policies", tags=["policies"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ─── schemas ──────────────────────────────────────────────────────────────────

class PolicyIn(BaseModel):
    slug: str
    display_name: str
    description: str | None = None
    effect: str = Field(pattern=r"^(allow|deny|require_approval)$")
    priority: int = 500
    actions: list[str] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list)
    condition: dict = Field(default_factory=dict)
    is_enabled: bool = True
    approval_email: str | None = None


class PolicyOut(PolicyIn):
    id: str


class BindingIn(BaseModel):
    subject_selector: str = Field(
        description="e.g. 'agent:<uuid>', 'user:<uuid>', 'role:<slug>', or '*'"
    )


class PolicyVersionOut(BaseModel):
    id: str
    version_number: int
    changed_by: str
    change_note: str | None
    created_at: str


class PolicyVersionDetailOut(PolicyVersionOut):
    snapshot: dict


# ─── helpers ──────────────────────────────────────────────────────────────────

def _policy_snapshot(p: Policy) -> dict:
    """Serialise all mutable policy fields to a plain dict."""
    return {
        "slug": p.slug,
        "display_name": p.display_name,
        "description": p.description,
        "effect": p.effect,
        "priority": p.priority,
        "actions": list(p.actions or []),
        "resource_types": list(p.resource_types or []),
        "condition": p.condition or {},
        "is_enabled": p.is_enabled,
        "approval_email": p.approval_email,
    }


async def _next_version_number(session: AsyncSession, policy_id: uuid.UUID) -> int:
    """Return the next version_number for a policy (SELECT MAX + 1, or 1 for first)."""
    max_ver = await session.scalar(
        select(func.max(PolicyVersion.version_number)).where(
            PolicyVersion.policy_id == policy_id
        )
    )
    return (max_ver or 0) + 1


async def _snapshot_policy(
    session: AsyncSession,
    policy: Policy,
    actor: str,
    change_note: str | None = None,
) -> PolicyVersion:
    """Capture the current policy state as a new PolicyVersion row."""
    ver = PolicyVersion(
        policy_id=policy.id,
        organization_id=policy.organization_id,
        version_number=await _next_version_number(session, policy.id),
        snapshot=_policy_snapshot(policy),
        changed_by=actor,
        change_note=change_note,
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(ver)
    await session.flush()
    return ver


# ─── CRUD endpoints ───────────────────────────────────────────────────────────

@router.get("", response_model=list[PolicyOut])
async def list_policies(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(Policy).where(Policy.organization_id == uuid.UUID(principal.org_id))
        .order_by(Policy.priority.asc())
    )).all()
    return [PolicyOut(id=str(r.id), **_policy_snapshot(r)) for r in rows]


@router.post("", response_model=PolicyOut, status_code=201)
async def create_policy(
    body: PolicyIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = Policy(
        organization_id=uuid.UUID(principal.org_id),
        slug=body.slug, display_name=body.display_name, description=body.description,
        effect=body.effect, priority=body.priority,
        actions=body.actions, resource_types=body.resource_types,
        condition=body.condition, is_enabled=body.is_enabled,
        approval_email=body.approval_email,
    )
    session.add(p)
    await session.flush()
    actor = f"user:{principal.user_id}" if principal.user_id else "system"
    await record_admin(
        session, org_id=principal.org_id,
        actor=actor,
        event_type="policy.created",
        resource_type="policy",
        resource_id=str(p.id),
        payload=body.model_dump(),
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(p)
    return PolicyOut(id=str(p.id), **_policy_snapshot(p))


@router.put("/{policy_id}", response_model=PolicyOut)
async def update_policy(
    policy_id: str, body: PolicyIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")

    actor = f"user:{principal.user_id}" if principal.user_id else "system"

    # Snapshot the PREVIOUS state before applying the change.
    await _snapshot_policy(session, p, actor=actor)

    for k, v in body.model_dump().items():
        setattr(p, k, v)
    await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=actor,
        event_type="policy.updated",
        resource_type="policy",
        resource_id=str(p.id),
        payload=body.model_dump(),
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(p)
    return PolicyOut(id=str(p.id), **_policy_snapshot(p))


# ─── versioning endpoints ─────────────────────────────────────────────────────

@router.get("/{policy_id}/versions", response_model=list[PolicyVersionOut])
async def list_versions(
    policy_id: str,
    principal: Principal = Depends(require_scope("policy.read")),
    session: AsyncSession = Depends(_session),
):
    """List all versions for a policy, newest first."""
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")

    rows = (await session.scalars(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == p.id)
        .order_by(PolicyVersion.version_number.desc())
    )).all()

    return [
        PolicyVersionOut(
            id=str(r.id),
            version_number=r.version_number,
            changed_by=r.changed_by,
            change_note=r.change_note,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/{policy_id}/versions/{version_number}", response_model=PolicyVersionDetailOut)
async def get_version(
    policy_id: str,
    version_number: int,
    principal: Principal = Depends(require_scope("policy.read")),
    session: AsyncSession = Depends(_session),
):
    """Return the full snapshot for a specific version."""
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")

    row = (await session.scalars(
        select(PolicyVersion).where(
            PolicyVersion.policy_id == p.id,
            PolicyVersion.version_number == version_number,
        )
    )).first()
    if not row:
        raise HTTPException(404, f"Version {version_number} not found for this policy")

    return PolicyVersionDetailOut(
        id=str(row.id),
        version_number=row.version_number,
        changed_by=row.changed_by,
        change_note=row.change_note,
        created_at=row.created_at.isoformat(),
        snapshot=row.snapshot,
    )


class RollbackIn(BaseModel):
    change_note: str | None = None


@router.post("/{policy_id}/rollback/{version_number}", response_model=PolicyOut)
async def rollback_policy(
    policy_id: str,
    version_number: int,
    body: RollbackIn,
    request: Request,
    principal: Principal = Depends(require_scope("policy.write")),
    session: AsyncSession = Depends(_session),
):
    """Restore the policy to a prior version's snapshot.

    The current state is snapshotted before overwriting (so rollback is itself
    versioned and reversible). An audit event policy.rolled_back is emitted.
    """
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")

    target_ver = (await session.scalars(
        select(PolicyVersion).where(
            PolicyVersion.policy_id == p.id,
            PolicyVersion.version_number == version_number,
        )
    )).first()
    if not target_ver:
        raise HTTPException(404, f"Version {version_number} not found for this policy")

    actor = f"user:{principal.user_id}" if principal.user_id else "system"
    note = body.change_note or f"rollback to version {version_number}"

    # Snapshot the current live state before overwriting.
    await _snapshot_policy(session, p, actor=actor, change_note=note)

    # Apply the target snapshot.
    snap = target_ver.snapshot
    for k, v in snap.items():
        setattr(p, k, v)
    await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=actor,
        event_type="policy.rolled_back",
        resource_type="policy",
        resource_id=str(p.id),
        payload={"rolled_back_to_version": version_number, "change_note": note},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    await session.refresh(p)
    return PolicyOut(id=str(p.id), **_policy_snapshot(p))


# ─── bindings endpoints ───────────────────────────────────────────────────────

@router.get("/{policy_id}/bindings")
async def list_bindings(
    policy_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")
    rows = (await session.scalars(
        select(PolicyBinding).where(PolicyBinding.policy_id == p.id)
    )).all()
    return [{"id": str(b.id), "subject_selector": b.subject_selector} for b in rows]


@router.delete("/{policy_id}/bindings/{binding_id}", status_code=204)
async def delete_binding(
    policy_id: str, binding_id: str, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")
    b = await session.get(PolicyBinding, uuid.UUID(binding_id))
    if not b or b.policy_id != p.id:
        raise HTTPException(404, "Binding not found")
    await session.delete(b)
    await session.commit()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="policy.unbound",
        resource_type="policy_binding",
        resource_id=binding_id,
        payload={"policy_id": policy_id, "subject_selector": b.subject_selector},
        ip_address=request.client.host if request.client else None,
    )
    return


@router.post("/{policy_id}/bindings", status_code=201)
async def bind_policy(
    policy_id: str, body: BindingIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")
    b = PolicyBinding(
        organization_id=p.organization_id,
        policy_id=p.id,
        subject_selector=body.subject_selector,
    )
    session.add(b)
    await session.flush()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="policy.bound",
        resource_type="policy_binding",
        resource_id=str(b.id),
        payload={"policy_id": policy_id, "subject_selector": body.subject_selector},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return {"binding_id": str(b.id)}
