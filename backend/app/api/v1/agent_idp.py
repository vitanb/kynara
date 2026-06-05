"""Agent identity-provider sync API (Okta).

Admins connect an Okta org and import its AI-agent identities into Kynara,
keeping them in sync and optionally mapping Okta groups to Kynara roles.

  GET    /idp/providers              list providers
  POST   /idp/providers             create a provider (token stored encrypted)
  GET    /idp/providers/{id}         provider detail
  PATCH  /idp/providers/{id}         update config (token optional)
  DELETE /idp/providers/{id}         remove provider
  POST   /idp/providers/{id}/test   verify connectivity + token
  POST   /idp/providers/{id}/sync   run a sync now
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, require_seat
from app.core.encryption import decrypt, encrypt
from app.db.session import SessionLocal
from app.idp.okta import OktaClient
from app.idp.sync import run_sync
from app.models.agent_idp import AgentIdentityProvider

router = APIRouter(prefix="/idp", tags=["identity-providers"])


async def _session():
    async with SessionLocal() as s:
        yield s


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="okta", pattern=r"^okta$")
    base_url: str = Field(min_length=1, max_length=512)
    api_token: str | None = None
    sync_mode: str = Field(default="agents", pattern=r"^(agents|group)$")
    group_id: str | None = None
    default_mode: str = Field(default="human_supervised",
                              pattern=r"^(human_supervised|autonomous|read_only)$")
    role_mapping: dict = Field(default_factory=dict)
    default_on_behalf_user_id: str | None = None
    deactivate_missing: bool = False
    is_enabled: bool = True


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_token: str | None = None  # only updates when provided
    sync_mode: str | None = Field(default=None, pattern=r"^(agents|group)$")
    group_id: str | None = None
    default_mode: str | None = Field(default=None,
                                     pattern=r"^(human_supervised|autonomous|read_only)$")
    role_mapping: dict | None = None
    default_on_behalf_user_id: str | None = None
    deactivate_missing: bool | None = None
    is_enabled: bool | None = None


def _out(p: AgentIdentityProvider) -> dict:
    return {
        "id": str(p.id), "name": p.name, "provider": p.provider, "base_url": p.base_url,
        "has_token": bool(p.api_token_enc), "sync_mode": p.sync_mode, "group_id": p.group_id,
        "default_mode": p.default_mode, "role_mapping": p.role_mapping or {},
        "default_on_behalf_user_id": str(p.default_on_behalf_user_id) if p.default_on_behalf_user_id else None,
        "deactivate_missing": p.deactivate_missing, "is_enabled": p.is_enabled,
        "last_synced_at": p.last_synced_at, "last_sync_status": p.last_sync_status,
        "last_sync_stats": p.last_sync_stats or {},
    }


async def _get_owned(session: AsyncSession, org_id: str, pid: str) -> AgentIdentityProvider:
    try:
        u = uuid.UUID(pid)
    except ValueError:
        raise HTTPException(400, "Invalid provider id")
    p = await session.get(AgentIdentityProvider, u)
    if not p or p.organization_id != uuid.UUID(org_id):
        raise HTTPException(404, "Provider not found")
    return p


@router.get("/providers")
async def list_providers(
    principal: Principal = Depends(require_seat("owner", "admin", "auditor")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(AgentIdentityProvider)
        .where(AgentIdentityProvider.organization_id == uuid.UUID(principal.org_id))
        .order_by(AgentIdentityProvider.created_at.desc())
    )).all()
    return [_out(p) for p in rows]


@router.post("/providers", status_code=201)
async def create_provider(
    body: ProviderIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = AgentIdentityProvider(
        organization_id=uuid.UUID(principal.org_id), provider=body.provider, name=body.name,
        base_url=body.base_url.rstrip("/"),
        api_token_enc=encrypt(body.api_token) if body.api_token else None,
        sync_mode=body.sync_mode, group_id=body.group_id, default_mode=body.default_mode,
        role_mapping=body.role_mapping or {},
        default_on_behalf_user_id=uuid.UUID(body.default_on_behalf_user_id) if body.default_on_behalf_user_id else None,
        deactivate_missing=body.deactivate_missing, is_enabled=body.is_enabled,
        created_by_user_id=uuid.UUID(principal.user_id) if principal.user_id else None,
    )
    session.add(p)
    await session.flush()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="idp.created", resource_type="agent_identity_provider", resource_id=str(p.id),
        payload={"provider": p.provider, "name": p.name, "base_url": p.base_url},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return _out(p)


@router.get("/providers/{pid}")
async def get_provider(
    pid: str,
    principal: Principal = Depends(require_seat("owner", "admin", "auditor")),
    session: AsyncSession = Depends(_session),
):
    return _out(await _get_owned(session, principal.org_id, pid))


@router.patch("/providers/{pid}")
async def update_provider(
    pid: str, body: ProviderUpdate,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await _get_owned(session, principal.org_id, pid)
    patch = body.model_dump(exclude_unset=True)
    if "api_token" in patch:
        token = patch.pop("api_token")
        p.api_token_enc = encrypt(token) if token else p.api_token_enc
    if "base_url" in patch and patch["base_url"]:
        patch["base_url"] = patch["base_url"].rstrip("/")
    if "default_on_behalf_user_id" in patch:
        v = patch.pop("default_on_behalf_user_id")
        p.default_on_behalf_user_id = uuid.UUID(v) if v else None
    for k, v in patch.items():
        setattr(p, k, v)
    await session.commit()
    return _out(p)


@router.delete("/providers/{pid}", status_code=204)
async def delete_provider(
    pid: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await _get_owned(session, principal.org_id, pid)
    await session.delete(p)
    await session.commit()
    return None


@router.post("/providers/{pid}/test")
async def test_provider(
    pid: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await _get_owned(session, principal.org_id, pid)
    if not p.api_token_enc:
        raise HTTPException(400, "No API token configured")
    client = OktaClient(p.base_url, decrypt(p.api_token_enc))
    try:
        return await client.test()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Okta connection failed: {e}")


@router.post("/providers/{pid}/sync")
async def sync_provider(
    pid: str, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    p = await _get_owned(session, principal.org_id, pid)
    if not p.is_enabled:
        raise HTTPException(400, "Provider is disabled")
    stats = await run_sync(session, p)
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="idp.synced", resource_type="agent_identity_provider", resource_id=str(p.id),
        payload=stats, ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return {"status": p.last_sync_status, "stats": stats, "synced_at": p.last_synced_at}
