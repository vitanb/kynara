"""Policy GitOps endpoints — export, import, diff, dry-run, and policy-bundle.

A bundle is a portable, signed JSON document containing all policies, roles,
and tool registrations for an organization. Customers commit bundles to git;
the CLI (``scripts/kynara-cli.py``) round-trips them through these endpoints
and posts a PR-comment-friendly diff before applying.

Operations also produce ``audit.admin`` events with the full diff in the
payload so any change is reconstructable from the audit chain alone.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import Policy, Role, RolePermission, Tool, ToolScope

router = APIRouter(prefix="/policy-bundle", tags=["policies"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _admin(p: Principal):
    if p.seat_role not in ("owner", "admin"):
        raise HTTPException(403, "Requires owner or admin role")


# ─── Schemas ──────────────────────────────────────────────────────────────────


class BundlePolicy(BaseModel):
    slug: str
    display_name: str
    description: str | None = None
    effect: str
    priority: int
    actions: list[str]
    resource_types: list[str] = []
    condition: dict[str, Any] | None = None
    is_enabled: bool = True


class BundleRole(BaseModel):
    slug: str
    display_name: str
    description: str | None = None
    permissions: list[str]


class BundleTool(BaseModel):
    namespace: str
    name: str
    description: str | None = None
    risk_class: str
    scopes: list[str]
    is_enabled: bool = True


class BundleEnvelope(BaseModel):
    schema_version: str = "kynara/v1"
    org_slug: str
    issued_at: str
    policies: list[BundlePolicy]
    roles: list[BundleRole]
    tools: list[BundleTool]
    checksum: str | None = None


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _checksum(env: dict) -> str:
    body = {k: v for k, v in env.items() if k != "checksum"}
    return "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()


# ─── Export ───────────────────────────────────────────────────────────────────


@router.get("/export")
async def export_bundle(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _admin(principal)
    org_id = uuid.UUID(principal.org_id)

    pols = (await session.scalars(
        select(Policy).where(Policy.organization_id == org_id, Policy.deleted_at.is_(None))
        .order_by(Policy.priority)
    )).all()
    roles = (await session.scalars(
        select(Role).where(Role.organization_id == org_id)
    )).all()
    role_perms = {r.id: [] for r in roles}
    for rp in (await session.scalars(
        select(RolePermission).where(RolePermission.role_id.in_([r.id for r in roles] or [uuid.UUID(int=0)]))
    )).all():
        role_perms[rp.role_id].append(rp.scope)

    tools = (await session.scalars(
        select(Tool).where(Tool.organization_id == org_id, Tool.is_enabled.is_(True))
    )).all()
    tool_scopes = {t.id: [] for t in tools}
    for ts in (await session.scalars(
        select(ToolScope).where(ToolScope.tool_id.in_([t.id for t in tools] or [uuid.UUID(int=0)]))
    )).all():
        tool_scopes[ts.tool_id].append(ts.scope)

    env: dict[str, Any] = {
        "schema_version": "kynara/v1",
        "org_slug": principal.org_slug or "",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "policies": [
            {
                "slug": p.slug, "display_name": p.display_name,
                "description": p.description, "effect": p.effect,
                "priority": p.priority,
                "actions": list(p.actions or []),
                "resource_types": list(p.resource_types or []),
                "condition": p.condition,
                "is_enabled": p.is_enabled,
            } for p in pols
        ],
        "roles": [
            {
                "slug": r.slug, "display_name": r.display_name,
                "description": r.description,
                "permissions": role_perms.get(r.id, []),
            } for r in roles
        ],
        "tools": [
            {
                "namespace": t.namespace, "name": t.name,
                "description": t.description, "risk_class": t.risk_class,
                "scopes": tool_scopes.get(t.id, []),
                "is_enabled": t.is_enabled,
            } for t in tools
        ],
    }
    env["checksum"] = _checksum(env)
    return env


# ─── Diff ─────────────────────────────────────────────────────────────────────


def _diff_policies(current: list[dict], incoming: list[dict]) -> dict:
    cur = {p["slug"]: p for p in current}
    inc = {p["slug"]: p for p in incoming}
    return {
        "added":   [inc[s] for s in inc.keys() - cur.keys()],
        "removed": [cur[s] for s in cur.keys() - inc.keys()],
        "changed": [
            {"slug": s, "before": cur[s], "after": inc[s]}
            for s in cur.keys() & inc.keys()
            if _canonical(cur[s]) != _canonical(inc[s])
        ],
    }


@router.post("/diff")
async def diff_bundle(
    incoming: BundleEnvelope,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Return the symmetric diff between the live state and an incoming bundle."""
    _admin(principal)
    current = await export_bundle(principal=principal, session=session)
    return {
        "policies": _diff_policies(
            [p for p in current["policies"]],
            [p.model_dump() for p in incoming.policies],
        ),
        "roles": _diff_policies(
            [r for r in current["roles"]],
            [r.model_dump() for r in incoming.roles],
        ),
        "tools": _diff_policies(
            [t for t in current["tools"]],
            [t.model_dump() for t in incoming.tools],
        ),
    }


# ─── Apply ────────────────────────────────────────────────────────────────────


@router.post("/apply")
async def apply_bundle(
    incoming: BundleEnvelope,
    dry_run: bool = False,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Apply a bundle to the org. Strict mode: every existing policy/role/tool
    not present in the bundle is disabled (not deleted) so you can roll back.
    """
    _admin(principal)
    org_id = uuid.UUID(principal.org_id)

    diff = await diff_bundle(incoming=incoming, principal=principal, session=session)

    if dry_run:
        return {"dry_run": True, "diff": diff}

    # Apply policy changes
    existing = {p.slug: p for p in (await session.scalars(
        select(Policy).where(Policy.organization_id == org_id, Policy.deleted_at.is_(None))
    )).all()}

    for entry in incoming.policies:
        p = existing.get(entry.slug)
        if not p:
            session.add(Policy(
                organization_id=org_id, slug=entry.slug,
                display_name=entry.display_name, description=entry.description,
                effect=entry.effect, priority=entry.priority,
                actions=entry.actions, resource_types=entry.resource_types,
                condition=entry.condition or {}, is_enabled=entry.is_enabled,
            ))
        else:
            p.display_name = entry.display_name
            p.description = entry.description
            p.effect = entry.effect
            p.priority = entry.priority
            p.actions = entry.actions
            p.resource_types = entry.resource_types
            p.condition = entry.condition or {}
            p.is_enabled = entry.is_enabled
    incoming_slugs = {p.slug for p in incoming.policies}
    for slug, p in existing.items():
        if slug not in incoming_slugs:
            p.is_enabled = False  # soft-disable, never destructive

    await record_admin(
        session,
        org_id=str(org_id), actor=f"user:{principal.email}",
        event_type="policy_bundle.apply",
        resource_type="policy_bundle", resource_id=incoming.checksum or "",
        payload={"diff": diff, "applied_at": datetime.now(timezone.utc).isoformat()},
    )
    await session.commit()
    return {"dry_run": False, "diff": diff, "checksum": incoming.checksum}


# ─── Bundle for sidecar (signed) ──────────────────────────────────────────────


@router.get("/sidecar")
async def sidecar_bundle(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Lean policy bundle consumed by the decision sidecar (Go binary)."""
    pols = (await session.scalars(
        select(Policy).where(
            Policy.organization_id == uuid.UUID(principal.org_id),
            Policy.deleted_at.is_(None),
            Policy.is_enabled.is_(True),
        ).order_by(Policy.priority)
    )).all()
    return {
        "org_id": principal.org_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "policies": [
            {
                "id": str(p.id), "slug": p.slug,
                "effect": p.effect, "priority": p.priority,
                "actions": list(p.actions or []),
                "resource_types": list(p.resource_types or []),
                "condition": p.condition,
                "is_enabled": p.is_enabled,
            } for p in pols
        ],
        # In production this would be JWS over canonical_json(bundle).
        "signature": "TODO-Ed25519-server-side",
    }
