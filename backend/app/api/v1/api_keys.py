"""API key CRUD — create, list, revoke org-scoped API keys.

Keys are shown in clear-text exactly once at creation. The DB stores
hmac_sha256(key, derived_key) so no key material is ever recoverable
server-side and offline brute-force requires the server secret.

Format:  sk_live_<64 hex chars>  (72 chars total, prefix from settings)
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal, require_seat
from app.auth.tokens import hash_api_key
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

AVAILABLE_SCOPES = {
    "audit.read",
    "decisions.check",
    "agents.read",
    "policies.read",
    "tools.read",
}


async def _session():
    async with SessionLocal() as s:
        yield s


# ── schemas ──────────────────────────────────────────────────────────────────

class CreateKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["audit.read"]
    expires_at: datetime | None = None


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    last_four: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked: bool


class CreateKeyResponse(ApiKeyOut):
    secret: str  # shown once only


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(ApiKey)
        .where(
            ApiKey.organization_id == uuid.UUID(principal.org_id),
            ApiKey.revoked.is_(False),
        )
        .order_by(ApiKey.created_at.desc())
    )).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateKeyRequest,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    # Validate scopes
    bad = set(body.scopes) - AVAILABLE_SCOPES
    if bad:
        raise HTTPException(400, f"Unknown scopes: {bad}. Available: {sorted(AVAILABLE_SCOPES)}")

    settings = get_settings()
    prefix = settings.api_key_prefix          # "sk_live_"
    raw_secret = prefix + secrets.token_hex(32)  # 72-char key

    key = ApiKey(
        organization_id=uuid.UUID(principal.org_id),
        created_by_user_id=uuid.UUID(principal.user_id),
        display_name=body.name,
        key_hash=hash_api_key(raw_secret),
        last_four=raw_secret[-4:],
        prefix=raw_secret[:12],              # "sk_live_xxxx" (first 12 chars)
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)

    out = _to_out(key)
    return CreateKeyResponse(**out.model_dump(), secret=raw_secret)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    key = await session.get(ApiKey, uuid.UUID(key_id))
    if not key or str(key.organization_id) != principal.org_id:
        raise HTTPException(404, "API key not found")
    key.revoked = True
    await session.commit()


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_out(k: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(k.id),
        name=k.display_name,
        prefix=k.prefix,
        last_four=k.last_four,
        scopes=k.scopes or [],
        created_at=k.created_at,
        last_used_at=k.last_used_at,
        expires_at=k.expires_at,
        revoked=k.revoked,
    )
