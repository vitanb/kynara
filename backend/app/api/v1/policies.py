"""Policy CRUD + binding management."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal, require_seat
from app.db.session import SessionLocal
from app.models import Policy, PolicyBinding

router = APIRouter(prefix="/policies", tags=["policies"])


async def _session():
    async with SessionLocal() as s:
        yield s


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


class PolicyOut(PolicyIn):
    id: str


class BindingIn(BaseModel):
    subject_selector: str = Field(description="e.g. 'agent:<uuid>', 'user:<uuid>', 'role:<slug>', or '*'")


@router.get("", response_model=list[PolicyOut])
async def list_policies(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(_session)):
    rows = (await session.scalars(
        select(Policy).where(Policy.organization_id == uuid.UUID(principal.org_id))
        .order_by(Policy.priority.asc())
    )).all()
    return [PolicyOut(id=str(r.id),
                      slug=r.slug, display_name=r.display_name, description=r.description,
                      effect=r.effect, priority=r.priority,
                      actions=list(r.actions or []),
                      resource_types=list(r.resource_types or []),
                      condition=r.condition or {}, is_enabled=r.is_enabled)
            for r in rows]


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
    )
    session.add(p)
    await session.flush()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="policy.created",
        resource_type="policy",
        resource_id=str(p.id),
        payload=body.model_dump(),
        ip_address=request.client.host if request.client else None,
    )
    return PolicyOut(id=str(p.id), **body.model_dump())


@router.put("/{policy_id}", response_model=PolicyOut)
async def update_policy(
    policy_id: str, body: PolicyIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await session.get(Policy, uuid.UUID(policy_id))
    if not p or p.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Policy not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    await session.flush()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="policy.updated",
        resource_type="policy",
        resource_id=str(p.id),
        payload=body.model_dump(),
        ip_address=request.client.host if request.client else None,
    )
    return PolicyOut(id=str(p.id), **body.model_dump())


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
    return {"binding_id": str(b.id)}
