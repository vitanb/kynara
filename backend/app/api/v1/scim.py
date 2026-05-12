"""SCIM 2.0 endpoints — RFC 7643/7644.

Authenticates with a per-org SCIM bearer token (issued from the SSO settings
page). All writes produce audit-log entries. Tenancy is enforced by RLS — the
session GUC is set after the token resolves to an org.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.passwords import hash_token
from app.db.session import SessionLocal
from app.models import OrgMembership, User
from app.models.sso import ScimSync, ScimToken

router = APIRouter(prefix="/scim/v2", tags=["scim"])

# ─── Auth + per-tenant session ────────────────────────────────────────────────


async def _scim_session(authorization: str | None = Header(None)) -> tuple[str, AsyncSession]:
    if not authorization or not authorization.startswith("Bearer "):
        raise _scim_err(401, "Missing SCIM bearer token")
    token = authorization[7:]
    th = hash_token(token)

    sess = SessionLocal()
    try:
        await sess.execute(text("SELECT set_config('app.org_id', '00000000-0000-0000-0000-000000000000', true)"))
        # Use ScimToken (the dedicated auth table) — ScimSync is only for event tracking
        row = (await sess.scalars(
            select(ScimToken).where(ScimToken.token_hash == th, ScimToken.is_enabled.is_(True))
        )).first()
        if not row:
            await sess.close()
            raise _scim_err(401, "Invalid SCIM token")
        org_id = str(row.organization_id)
        await sess.execute(
            text("SELECT set_config('app.org_id', :v, true)").bindparams(v=org_id),
        )
        # Update last_used_at (best-effort)
        try:
            from datetime import datetime, timezone as _tz
            row.last_used_at = datetime.now(tz=_tz.utc)
            await sess.flush()
        except Exception:
            pass
        return org_id, sess
    except HTTPException:
        await sess.close()
        raise


def _sanitize_err_detail(detail: str) -> str:
    """Truncate and strip control characters from error details.

    Prevents reflected user-input from inflating logs or carrying injection
    payloads across log aggregators (F-06 remediation).
    """
    # Strip non-printable / control characters
    cleaned = "".join(c for c in detail if c.isprintable() or c in (" ", "\t"))
    # Truncate so log lines stay bounded
    return cleaned[:256]


def _scim_err(status: int, detail: str, scim_type: str | None = None) -> HTTPException:
    payload: dict[str, Any] = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "status": str(status),
        "detail": _sanitize_err_detail(detail),
    }
    if scim_type:
        # scimType is a fixed enum per RFC 7644 — don't echo user input here
        allowed_scim_types = {
            "uniqueness", "tooMany", "mutability", "sensitive",
            "invalidSyntax", "invalidFilter", "invalidValue",
            "invalidPath", "noTarget", "invalidVers", "multiValued",
        }
        payload["scimType"] = scim_type if scim_type in allowed_scim_types else "invalidValue"
    return HTTPException(status_code=status, detail=payload)


# ─── Filter parsing (RFC 7644 §3.4.2.2 — common subset) ──────────────────────

_FILTER_RE = re.compile(
    r'(?P<attr>[A-Za-z][A-Za-z0-9.]*)\s+(?P<op>eq|ne|co|sw|ew|gt|ge|lt|le|pr)'
    r'(?:\s+"(?P<val>[^"]*)")?'
)
_FIELD_MAP = {
    "userName": User.email,
    "emails.value": User.email,
    "displayName": User.display_name,
    "active": User.is_active,
}


def _apply_filter(filt: str | None):
    if not filt:
        return None
    m = _FILTER_RE.match(filt.strip())
    if not m:
        raise _scim_err(400, f"Unsupported filter: {filt}", "invalidFilter")
    attr, op, val = m.group("attr"), m.group("op"), m.group("val")
    col = _FIELD_MAP.get(attr)
    if col is None:
        raise _scim_err(400, f"Unsupported attribute: {attr}", "invalidPath")
    if op == "eq":
        if attr == "active":
            return col.is_(val == "true")
        return col == val
    if op == "ne":
        return col != val
    if op == "co":
        return col.ilike(f"%{val}%")
    if op == "sw":
        return col.ilike(f"{val}%")
    if op == "ew":
        return col.ilike(f"%{val}")
    if op == "pr":
        return col.is_not(None)
    raise _scim_err(400, f"Unsupported operator: {op}", "invalidFilter")


# ─── Serialisation ────────────────────────────────────────────────────────────


def _scim_user(u: User) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(u.id),
        "userName": u.email,
        "displayName": u.display_name,
        "name": {"formatted": u.display_name or u.email},
        "emails": [{"value": u.email, "primary": True}],
        "active": u.is_active,
        "meta": {
            "resourceType": "User",
            "created": u.created_at.isoformat() if u.created_at else None,
            "lastModified": u.updated_at.isoformat() if u.updated_at else None,
            "version": f'W/"{u.updated_at.timestamp():.0f}"' if u.updated_at else None,
            "location": f"/scim/v2/Users/{u.id}",
        },
    }


def _list_resp(items: list[dict], total: int, start: int, count: int) -> dict:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total,
        "startIndex": start,
        "itemsPerPage": count,
        "Resources": items,
    }


# ─── Discovery endpoints ──────────────────────────────────────────────────────


@router.get("/ServiceProviderConfig")
async def service_provider_config():
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch":           {"supported": True},
        "bulk":            {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter":          {"supported": True, "maxResults": 200},
        "changePassword":  {"supported": False},
        "sort":            {"supported": False},
        "etag":            {"supported": True},
        "authenticationSchemes": [{
            "type": "oauthbearertoken", "name": "OAuth Bearer Token", "primary": True,
        }],
    }


@router.get("/ResourceTypes")
async def resource_types():
    return [
        {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
         "id": "User", "name": "User", "endpoint": "/Users",
         "schema": "urn:ietf:params:scim:schemas:core:2.0:User"},
        {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
         "id": "Group", "name": "Group", "endpoint": "/Groups",
         "schema": "urn:ietf:params:scim:schemas:core:2.0:Group"},
    ]


# ─── Users ────────────────────────────────────────────────────────────────────


@router.get("/Users")
async def list_users(
    filter: str | None = Query(None),
    startIndex: int = Query(1, ge=1),
    count: int = Query(50, ge=1, le=200),
    ctx: tuple[str, AsyncSession] = Depends(_scim_session),
):
    org_id, sess = ctx
    async with sess as s:
        clause = _apply_filter(filter)
        q = (
            select(User)
            .join(OrgMembership, OrgMembership.user_id == User.id)
            .where(OrgMembership.organization_id == uuid.UUID(org_id))
        )
        if clause is not None:
            q = q.where(clause)
        total = await s.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = (await s.scalars(
            q.order_by(User.created_at).offset(startIndex - 1).limit(count)
        )).all()
        return _list_resp([_scim_user(u) for u in rows], total, startIndex, len(rows))


@router.get("/Users/{user_id}")
async def get_user(user_id: str, ctx: tuple[str, AsyncSession] = Depends(_scim_session)):
    _, sess = ctx
    async with sess as s:
        u = await s.get(User, uuid.UUID(user_id))
        if not u:
            raise _scim_err(404, "User not found")
        return _scim_user(u)


@router.post("/Users", status_code=201)
async def create_user(body: dict, ctx: tuple[str, AsyncSession] = Depends(_scim_session)):
    org_id, sess = ctx
    email = body.get("userName") or (body.get("emails") or [{}])[0].get("value")
    if not email:
        raise _scim_err(400, "Missing userName/emails.value", "invalidValue")
    display = body.get("displayName") or (body.get("name") or {}).get("formatted") or email

    async with sess as s:
        existing = (await s.scalars(
            select(User)
            .join(OrgMembership, OrgMembership.user_id == User.id)
            .where(User.email == email,
                   OrgMembership.organization_id == uuid.UUID(org_id))
        )).first()
        if existing:
            existing.is_active = bool(body.get("active", True))
            await s.commit()
            return _scim_user(existing)

        u = User(email=email, display_name=display, is_active=bool(body.get("active", True)))
        s.add(u)
        await s.flush()
        s.add(OrgMembership(
            organization_id=uuid.UUID(org_id), user_id=u.id,
            seat_role="member", is_active=True,
        ))
        await record_admin(
            s,
            org_id=org_id, actor="scim",
            event_type="scim.user.create",
            resource_type="user", resource_id=str(u.id),
            payload={"email": email},
        )
        await s.commit()
        return _scim_user(u)


@router.put("/Users/{user_id}")
async def replace_user(user_id: str, body: dict, ctx: tuple[str, AsyncSession] = Depends(_scim_session)):
    org_id, sess = ctx
    async with sess as s:
        u = await s.get(User, uuid.UUID(user_id))
        if not u:
            raise _scim_err(404, "User not found")
        u.email = body.get("userName") or u.email
        u.display_name = body.get("displayName") or u.display_name
        u.is_active = bool(body.get("active", u.is_active))
        await record_admin(
            s,
            org_id=org_id, actor="scim", event_type="scim.user.replace",
            resource_type="user", resource_id=str(u.id),
            payload={"active": u.is_active},
        )
        await s.commit()
        return _scim_user(u)


@router.patch("/Users/{user_id}")
async def patch_user(user_id: str, body: dict, ctx: tuple[str, AsyncSession] = Depends(_scim_session)):
    org_id, sess = ctx
    async with sess as s:
        u = await s.get(User, uuid.UUID(user_id))
        if not u:
            raise _scim_err(404, "User not found")
        for op in body.get("Operations", []):
            name = (op.get("op") or "").lower()
            path = op.get("path") or ""
            value = op.get("value")
            if name not in ("add", "replace", "remove"):
                raise _scim_err(400, f"Bad op: {name}", "invalidValue")
            if path in ("active",) or (path == "" and isinstance(value, dict) and "active" in value):
                v = value if path == "active" else value["active"]
                u.is_active = bool(v) if name != "remove" else False
            elif path == "displayName":
                u.display_name = None if name == "remove" else value
            elif path == "userName":
                if name != "remove":
                    u.email = value
        await record_admin(
            s,
            org_id=org_id, actor="scim", event_type="scim.user.patch",
            resource_type="user", resource_id=str(u.id),
            payload={"ops": body.get("Operations", [])},
        )
        await s.commit()
        return _scim_user(u)


@router.delete("/Users/{user_id}", status_code=204)
async def delete_user(user_id: str, ctx: tuple[str, AsyncSession] = Depends(_scim_session)):
    """Soft-delete: deactivate. Hard-delete is never exposed via SCIM."""
    org_id, sess = ctx
    async with sess as s:
        u = await s.get(User, uuid.UUID(user_id))
        if not u:
            raise _scim_err(404, "User not found")
        u.is_active = False
        if hasattr(u, "deactivated_at"):
            u.deactivated_at = datetime.now(timezone.utc)
        await record_admin(
            s,
            org_id=org_id, actor="scim", event_type="scim.user.deactivate",
            resource_type="user", resource_id=str(u.id),
            payload={"via": "scim.delete"},
        )
        await s.commit()


# ─── Groups ───────────────────────────────────────────────────────────────────


@router.get("/Groups")
async def list_groups(_ctx: tuple[str, AsyncSession] = Depends(_scim_session)):
    return _list_resp(
        items=[
            {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
             "id": role, "displayName": role,
             "meta": {"resourceType": "Group"}}
            for role in ("admin", "developer", "auditor", "member")
        ],
        total=4, start=1, count=4,
    )
