"""Role management — CRUD for roles and their scope permissions.

Roles are the RBAC layer: a named set of scopes you can assign to an agent
via AgentAssignment. The engine unions scopes from all active role assignments
before running the ABAC policy pass.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal, require_seat
from app.db.session import SessionLocal
from app.models import AgentAssignment, Role, RolePermission
from app.webhooks.service import emit as emit_webhook

router = APIRouter(prefix="/roles", tags=["roles"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


async def _session():
    async with SessionLocal() as s:
        yield s


# ── schemas ───────────────────────────────────────────────────────────────────

class RoleIn(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scopes: list[str] = Field(default_factory=list)


class RoleOut(BaseModel):
    id: str
    slug: str
    display_name: str
    description: str | None
    scopes: list[str]
    is_system: bool


class RoleUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    scopes: list[str] | None = None   # None = don't touch; [] = clear all


# ── helpers ───────────────────────────────────────────────────────────────────

async def _to_out(session: AsyncSession, role: Role) -> RoleOut:
    scopes = (await session.scalars(
        select(RolePermission.scope).where(RolePermission.role_id == role.id)
    )).all()
    return RoleOut(
        id=str(role.id),
        slug=role.slug,
        display_name=role.display_name,
        description=role.description,
        scopes=sorted(scopes),
        is_system=role.is_system,
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RoleOut])
async def list_roles(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """List all roles in the org (readable by all seat roles)."""
    rows = (await session.scalars(
        select(Role)
        .where(Role.organization_id == uuid.UUID(principal.org_id))
        .order_by(Role.display_name)
    )).all()
    return [await _to_out(session, r) for r in rows]


@router.post("", response_model=RoleOut, status_code=201)
async def create_role(
    body: RoleIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    if not _SLUG_RE.match(body.slug):
        raise HTTPException(422, "slug must be lowercase alphanumeric, hyphens, underscores")

    existing = await session.scalar(
        select(Role).where(
            Role.organization_id == uuid.UUID(principal.org_id),
            Role.slug == body.slug,
        )
    )
    if existing:
        raise HTTPException(409, f"Role with slug '{body.slug}' already exists")

    role = Role(
        organization_id=uuid.UUID(principal.org_id),
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
    )
    session.add(role)
    await session.flush()

    for scope in body.scopes:
        session.add(RolePermission(role_id=role.id, scope=scope.strip()))
    await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}",
        event_type="role.created",
        resource_type="role", resource_id=str(role.id),
        payload={"slug": body.slug, "scopes": body.scopes},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return await _to_out(session, role)


@router.get("/{role_id}", response_model=RoleOut)
async def get_role(
    role_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    role = await session.get(Role, uuid.UUID(role_id))
    if not role or role.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Role not found")
    return await _to_out(session, role)


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: str, body: RoleUpdate, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    role = await session.get(Role, uuid.UUID(role_id))
    if not role or role.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Role not found")
    if role.is_system:
        raise HTTPException(403, "System roles cannot be modified")

    if body.display_name is not None:
        role.display_name = body.display_name
    if body.description is not None:
        role.description = body.description

    if body.scopes is not None:
        # Replace scopes
        existing_perms = (await session.scalars(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )).all()
        for p in existing_perms:
            await session.delete(p)
        await session.flush()
        for scope in body.scopes:
            session.add(RolePermission(role_id=role.id, scope=scope.strip()))
        await session.flush()

    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}",
        event_type="role.updated",
        resource_type="role", resource_id=role_id,
        payload={"display_name": body.display_name, "scopes": body.scopes},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()

    # If scopes changed, notify every agent that has an active assignment on this role
    if body.scopes is not None:
        affected_agent_ids = (await session.scalars(
            select(AgentAssignment.agent_id).where(
                AgentAssignment.role_id == uuid.UUID(role_id),
                AgentAssignment.is_active.is_(True),
            )
        )).all()
        for agent_id in set(affected_agent_ids):
            await emit_webhook(
                session, org_id=principal.org_id,
                event_type="agent.permissions_changed",
                payload={
                    "agent_id": str(agent_id),
                    "change": "role_scopes_updated",
                    "role_id": role_id,
                    "role_slug": role.slug,
                    "new_scopes": body.scopes,
           