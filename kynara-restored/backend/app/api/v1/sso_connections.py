"""SSO connection management endpoints.

CRUD for SsoConnection records. The actual OIDC/SAML login flows live in sso.py.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, require_seat
from app.db.session import SessionLocal
from app.models import SsoConnection

router = APIRouter(prefix="/sso/connections", tags=["sso"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", s.lower()).strip("-")[:60]


class ConnectionIn(BaseModel):
    provider: str
    protocol: str           # "oidc" | "saml"
    domain: str = ""        # email domain for routing, e.g. "acme.com"
    # OIDC
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    # SAML
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_x509: str = ""
    # Attribute mapping
    attribute_mapping_email: str = "email"
    attribute_mapping_name: str = "name"
    attribute_mapping_groups: str = "groups"


class ConnectionPatch(BaseModel):
    is_enabled: bool | None = None
    enforce_for_org: bool | None = None


@router.get("")
async def list_connections(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(SsoConnection)
        .where(SsoConnection.organization_id == uuid.UUID(principal.org_id))
        .order_by(SsoConnection.created_at)
    )).all()
    return [_serialize(r) for r in rows]


@router.post("", status_code=201)
async def create_connection(
    body: ConnectionIn,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    if body.protocol not in ("oidc", "saml"):
        raise HTTPException(422, "protocol must be 'oidc' or 'saml'")

    slug = _slugify(f"{body.provider}-{body.protocol}")
    # Ensure uniqueness within the org
    existing = await session.scalar(
        select(SsoConnection).where(
            SsoConnection.organization_id == uuid.UUID(principal.org_id),
            SsoConnection.slug == slug,
        )
    )
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    conn = SsoConnection(
        organization_id=uuid.UUID(principal.org_id),
        slug=slug,
        protocol=body.protocol,
        display_name=body.provider.replace("-", " ").title(),
        # OIDC
        issuer=body.issuer or None,
        client_id=body.client_id or None,
        # NOTE: production systems should encrypt this at rest (e.g. AES-GCM with KMS).
        # Stored plaintext here for simplicity; scope it via env-level secret management.
        client_secret_enc=body.client_secret or None,
        # SAML
        idp_entity_id=body.idp_entity_id or None,
        idp_sso_url=body.idp_sso_url or None,
        idp_x509_cert=body.idp_x509 or None,
        # Attribute mapping
        attribute_map={
            "email":  body.attribute_mapping_email,
            "name":   body.attribute_mapping_name,
            "groups": body.attribute_mapping_groups,
        },
        email_domain_allowlist=[body.domain] if body.domain else [],
        is_enabled=True,
        enforce_for_org=False,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return _serialize(conn)


@router.put("/{connection_id}")
async def update_connection(
    connection_id: str,
    body: ConnectionIn,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Full update of a connection's config (owner or admin)."""
    conn = await _get_conn(connection_id, principal.org_id, session)
    conn.display_name = body.provider.replace("-", " ").title() if body.provider else conn.display_name
    if body.domain is not None:
        conn.email_domain_allowlist = [body.domain] if body.domain else []
    if body.issuer:
        conn.issuer = body.issuer
    if body.client_id:
        conn.client_id = body.client_id
    if body.client_secret:
        conn.client_secret_enc = body.client_secret
    if body.idp_entity_id:
        conn.idp_entity_id = body.idp_entity_id
    if body.idp_sso_url:
        conn.idp_sso_url = body.idp_sso_url
    if body.idp_x509:
        conn.idp_x509_cert = body.idp_x509
    conn.attribute_map = {
        "email":  body.attribute_mapping_email or conn.attribute_map.get("email", "email"),
        "name":   body.attribute_mapping_name  or conn.attribute_map.get("name", "name"),
        "groups": body.attribute_mapping_groups or conn.attribute_map.get("groups", "groups"),
    }
    await session.commit()
    await session.refresh(conn)
    return _serialize(conn)


@router.patch("/{connection_id}")
async def patch_connection(
    connection_id: str,
    body: ConnectionPatch,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Toggle is_enabled / enforce_for_org without touching other fields."""
    conn = await _get_conn(connection_id, principal.org_id, session)
    if body.is_enabled is not None:
        conn.is_enabled = body.is_enabled
    if body.enforce_for_org is not None:
        conn.enforce_for_org = body.enforce_for_org
    await session.commit()
    await session.refresh(conn)
    return _serialize(conn)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    principal: Principal = Depends(require_seat("owner")),
    session: AsyncSession = Depends(_session),
):
    conn = await _get_conn(connection_id, principal.org_id, session)
    await session.delete(conn)
    await session.commit()


# ── helpers ────────────────────────────────────────────────────────────────

async def _get_conn(connection_id: str, org_id: str, session: AsyncSession) -> SsoConnection:
    try:
        cid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(422, "Invalid connection ID")
    conn = await session.scalar(
        select(SsoConnection).where(
            SsoConnection.id == cid,
            SsoConnection.organization_id == uuid.UUID(org_id),
        )
    )
    if not conn:
        raise HTTPException(404, "SSO connection not found")
    return conn


def _serialize(conn: SsoConnection) -> dict:
    domain = (conn.email_domain_allowlist or [""])[0]
    attr = conn.attribute_map or {}
    return {
        "id":               str(conn.id),
        "slug":             conn.slug,
        "provider":         conn.display_name,
        "protocol":         conn.protocol,
        "domain":           domain,
        # OIDC
        "issuer":           conn.issuer or "",
        "client_id":        conn.client_id or "",
        # Never expose secret — indicate whether one is set
        "client_secret_set": bool(conn.client_secret_enc),
        # SAML
        "idp_entity_id":    conn.idp_entity_id or "",
        "idp_sso_url":      conn.idp_sso_url or "",
        "idp_x509_cert":    conn.idp_x509_cert or "",
        # Attribute mapping
        "attribute_mapping_email":  attr.get("email", "email"),
        "attribute_mapping_name":   attr.get("name", "name"),
        "attribute_mapping_groups": attr.get("groups", "groups"),
        # Flags
        "is_enabled":       conn.is_enabled,
        "enforce_for_org":  conn.enforce_for_org,
        "created_at":       conn.created_at.isoformat() if conn.created_at else None,
    }
