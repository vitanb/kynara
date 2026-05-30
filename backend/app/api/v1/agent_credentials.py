"""Agent Identity and Credential Management endpoints.

Supports issuing, listing, revoking, and rotating agent credentials.
Two credential types are supported:
  - api_key: a ``kag_`` prefixed token, hash-stored (SHA-256)
  - mtls_cert: a self-signed X.509 certificate + private key returned once
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, require_seat
from app.db.session import SessionLocal
from app.models import Agent
from app.models.agent_credential import AgentCredential

router = APIRouter(prefix="/agents", tags=["agent-credentials"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ─── Schemas ──────────────────────────────────────────────────────────────────


class CredentialIssueIn(BaseModel):
    credential_type: str = "api_key"  # "api_key" | "mtls_cert"
    expires_at: datetime | None = None
    metadata: dict[str, Any] = {}


class CredentialIssueOut(BaseModel):
    id: str
    credential_type: str
    key_prefix: str
    expires_at: datetime | None
    created_at: datetime
    # Returned ONCE — only present at issuance
    plaintext_key: str | None = None
    certificate_pem: str | None = None
    private_key_pem: str | None = None


class CredentialListItem(BaseModel):
    id: str
    credential_type: str
    key_prefix: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_active: bool
    created_at: datetime


class RotateResult(BaseModel):
    revoked_id: str
    new_credential: CredentialIssueOut


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _issue_api_key() -> tuple[str, str, str]:
    """Returns (plaintext, key_prefix, key_hash)."""
    raw = f"kag_{secrets.token_urlsafe(32)}"
    return raw, raw[:8], _hash_key(raw)


def _issue_mtls_cert(agent_id: str, org_id: str) -> tuple[str, str, str, str]:
    """Generate a self-signed X.509 cert.

    Returns (cert_pem, private_key_pem, key_prefix, key_hash).
    key_hash is the SHA-256 of the cert's PEM bytes for storage/lookup.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
        import datetime as dt
    except ImportError:
        raise HTTPException(500, "cryptography library not installed; cannot issue mTLS cert")

    private_key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"kynara-agent:{agent_id}"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, f"kynara-org:{org_id}"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(year=now.year + 1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()

    key_hash = _hash_key(cert_pem)
    # Use the first 8 chars of the serial number hex as prefix
    prefix = f"kac_{cert.serial_number:016x}"[:8]
    return cert_pem, key_pem, prefix, key_hash


async def _get_agent_or_404(agent_id: str, org_id: str, session: AsyncSession) -> Agent:
    agent = await session.get(Agent, uuid.UUID(agent_id))
    if not agent or str(agent.organization_id) != org_id:
        raise HTTPException(404, "Agent not found")
    return agent


def _cred_to_list_item(c: AgentCredential) -> CredentialListItem:
    return CredentialListItem(
        id=str(c.id),
        credential_type=c.credential_type,
        key_prefix=c.key_prefix,
        expires_at=c.expires_at,
        last_used_at=c.last_used_at,
        revoked_at=c.revoked_at,
        is_active=c.is_active,
        created_at=c.created_at,
    )


async def _do_issue(
    agent: Agent,
    body: CredentialIssueIn,
    session: AsyncSession,
    actor: str,
) -> CredentialIssueOut:
    org_id = str(agent.organization_id)
    agent_id = str(agent.id)

    if body.credential_type == "api_key":
        plaintext, prefix, key_hash = _issue_api_key()
        cred = AgentCredential(
            organization_id=agent.organization_id,
            agent_id=agent.id,
            credential_type="api_key",
            key_prefix=prefix,
            key_hash=key_hash,
            expires_at=body.expires_at,
            metadata_=body.metadata,
        )
        session.add(cred)
        await session.flush()
        await record_admin(
            session,
            org_id=org_id,
            actor=actor,
            event_type="agent.credential.issued",
            resource_type="agent_credential",
            resource_id=str(cred.id),
            payload={"agent_id": agent_id, "type": "api_key", "prefix": prefix},
        )
        await session.commit()
        return CredentialIssueOut(
            id=str(cred.id),
            credential_type="api_key",
            key_prefix=prefix,
            expires_at=cred.expires_at,
            created_at=cred.created_at,
            plaintext_key=plaintext,
        )

    elif body.credential_type == "mtls_cert":
        cert_pem, key_pem, prefix, key_hash = _issue_mtls_cert(agent_id, org_id)
        cred = AgentCredential(
            organization_id=agent.organization_id,
            agent_id=agent.id,
            credential_type="mtls_cert",
            key_prefix=prefix,
            key_hash=key_hash,
            expires_at=body.expires_at,
            metadata_=body.metadata,
        )
        session.add(cred)
        await session.flush()
        await record_admin(
            session,
            org_id=org_id,
            actor=actor,
            event_type="agent.credential.issued",
            resource_type="agent_credential",
            resource_id=str(cred.id),
            payload={"agent_id": agent_id, "type": "mtls_cert", "prefix": prefix},
        )
        await session.commit()
        return CredentialIssueOut(
            id=str(cred.id),
            credential_type="mtls_cert",
            key_prefix=prefix,
            expires_at=cred.expires_at,
            created_at=cred.created_at,
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
        )

    else:
        raise HTTPException(400, f"Unknown credential_type: {body.credential_type}")


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/{agent_id}/credentials", response_model=CredentialIssueOut, status_code=201)
async def issue_credential(
    agent_id: str,
    body: CredentialIssueIn,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Issue a new credential for an agent. The plaintext key is returned ONCE."""
    agent = await _get_agent_or_404(agent_id, principal.org_id, session)
    actor = f"user:{principal.user_id}"
    return await _do_issue(agent, body, session, actor)


@router.get("/{agent_id}/credentials", response_model=list[CredentialListItem])
async def list_credentials(
    agent_id: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """List credentials for an agent. Never returns the plaintext key."""
    await _get_agent_or_404(agent_id, principal.org_id, session)
    rows = (await session.scalars(
        select(AgentCredential)
        .where(
            AgentCredential.agent_id == uuid.UUID(agent_id),
            AgentCredential.organization_id == uuid.UUID(principal.org_id),
        )
        .order_by(AgentCredential.created_at.desc())
    )).all()
    return [_cred_to_list_item(c) for c in rows]


@router.delete("/{agent_id}/credentials/{credential_id}", status_code=204)
async def revoke_credential(
    agent_id: str,
    credential_id: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Revoke a credential — sets revoked_at and is_active=False."""
    await _get_agent_or_404(agent_id, principal.org_id, session)
    cred = await session.get(AgentCredential, uuid.UUID(credential_id))
    if not cred or str(cred.agent_id) != agent_id or str(cred.organization_id) != principal.org_id:
        raise HTTPException(404, "Credential not found")
    if not cred.is_active:
        raise HTTPException(400, "Credential is already revoked")

    actor = f"user:{principal.user_id}"
    cred.revoked_at = datetime.now(timezone.utc)
    cred.revoked_by = actor
    cred.is_active = False

    await record_admin(
        session,
        org_id=principal.org_id,
        actor=actor,
        event_type="agent.credential.revoked",
        resource_type="agent_credential",
        resource_id=credential_id,
        payload={"agent_id": agent_id, "type": cred.credential_type},
    )
    await session.commit()


@router.post("/{agent_id}/credentials/{credential_id}/rotate", response_model=RotateResult)
async def rotate_credential(
    agent_id: str,
    credential_id: str,
    body: CredentialIssueIn = CredentialIssueIn(),
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Revoke old credential and issue a new one in a single atomic operation."""
    agent = await _get_agent_or_404(agent_id, principal.org_id, session)
    cred = await session.get(AgentCredential, uuid.UUID(credential_id))
    if not cred or str(cred.agent_id) != agent_id or str(cred.organization_id) != principal.org_id:
        raise HTTPException(404, "Credential not found")
    if not cred.is_active:
        raise HTTPException(400, "Credential is already revoked")

    actor = f"user:{principal.user_id}"

    # Revoke old
    cred.revoked_at = datetime.now(timezone.utc)
    cred.revoked_by = actor
    cred.is_active = False
    await session.flush()

    # Use the same type as the old credential unless overridden
    if not body.credential_type or body.credential_type == "api_key":
        body = CredentialIssueIn(
            credential_type=cred.credential_type,
            expires_at=body.expires_at or cred.expires_at,
            metadata=body.metadata or cred.metadata_,
        )

    new_cred = await _do_issue(agent, body, session, actor)

    return RotateResult(revoked_id=credential_id, new_credential=new_cred)
