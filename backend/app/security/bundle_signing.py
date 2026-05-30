"""Ed25519 policy-bundle signing and verification.

Each organisation has a per-org Ed25519 keypair.  The private key is stored
envelope-encrypted in the ``tenant_keys`` table via the KMS abstraction layer
(see ``app.security.kms``); the public key is stored in plaintext so the Go
sidecar can fetch it without KMS access.

Signing flow (server-side, called from the bundle endpoint):
    1. Serialise the bundle body to canonical JSON (sorted keys, no whitespace).
    2. Sign the canonical JSON with the org's Ed25519 private key.
    3. Embed the base64-encoded signature in the bundle as ``"signature"``.

Verification flow (sidecar or client):
    1. Strip the ``"signature"`` field from the bundle.
    2. Re-serialise to canonical JSON.
    3. Verify with the org's Ed25519 public key from ``GET /bundle/pubkey``.

Key rotation: generating a new keypair invalidates all bundles in-flight.
The sidecar should re-fetch the bundle immediately after the rotation event.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid as _uuid

log = logging.getLogger("kynara.bundle_signing")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def _require_crypto() -> None:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError(
            "cryptography>=42.0 is required for bundle signing. "
            "Add it to pyproject.toml dependencies."
        )


# ---------------------------------------------------------------------------
# Canonical JSON serialisation
# ---------------------------------------------------------------------------

def canonical_json(obj: dict) -> bytes:
    """Deterministic JSON bytes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def generate_keypair() -> tuple[bytes, bytes]:
    """Return ``(private_key_pem, public_key_pem)`` as bytes."""
    _require_crypto()
    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    return priv_pem, pub_pem


# ---------------------------------------------------------------------------
# Sign / verify
# ---------------------------------------------------------------------------

def sign_bundle(bundle: dict, private_key_pem: bytes) -> dict:
    """Return a copy of *bundle* with ``"signature"`` set to a base64 Ed25519 sig.

    The ``"signature"`` field is excluded from the signed payload so callers
    can verify by simply popping the field before re-serialising.
    """
    _require_crypto()
    payload = {k: v for k, v in bundle.items() if k != "signature"}
    msg = canonical_json(payload)

    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    priv = load_pem_private_key(private_key_pem, password=None)
    sig = priv.sign(msg)  # Ed25519 — no hash param needed
    signed = dict(bundle)
    signed["signature"] = base64.b64encode(sig).decode()
    log.debug("bundle_signing.signed", sig_len=len(sig))
    return signed


def verify_bundle(bundle: dict, public_key_pem: bytes) -> bool:
    """Verify the ``"signature"`` in *bundle* against the canonical payload.

    Returns ``True`` on success.  Raises ``ValueError`` on invalid signature
    or ``RuntimeError`` if the crypto library is unavailable.
    """
    _require_crypto()
    sig_b64 = bundle.get("signature", "")
    if not sig_b64:
        raise ValueError("bundle has no 'signature' field")
    try:
        sig = base64.b64decode(sig_b64)
    except Exception as exc:
        raise ValueError(f"signature is not valid base64: {exc}") from exc

    payload = {k: v for k, v in bundle.items() if k != "signature"}
    msg = canonical_json(payload)

    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.exceptions import InvalidSignature
    pub = load_pem_public_key(public_key_pem)
    try:
        pub.verify(sig, msg)
        log.debug("bundle_signing.verified_ok")
        return True
    except InvalidSignature as exc:
        raise ValueError("bundle signature verification failed") from exc


# ---------------------------------------------------------------------------
# Async helpers for endpoint use (load key from DB / KMS)
# ---------------------------------------------------------------------------

async def get_or_create_org_keypair(
    session,
    org_id: str,
) -> tuple[bytes, bytes]:
    """Return ``(private_key_pem, public_key_pem)`` for the org, creating if absent.

    The private key is stored envelope-encrypted in ``tenant_keys`` using the
    KMS abstraction.  The public key is stored in plaintext in the same row
    under the ``metadata`` JSONB column (field ``"bundle_signing_pub_pem"``).
    """
    from sqlalchemy import select
    from app.models.security import TenantKey  # noqa: PLC0415
    from app.security.kms import encrypt_for_tenant, decrypt_for_tenant  # noqa: PLC0415
    import base64 as _b64

    PURPOSE = "bundle_signing"

    row = await session.scalar(
        select(TenantKey).where(
            TenantKey.organization_id == _uuid.UUID(org_id),
            TenantKey.purpose == PURPOSE,
        )
    )

    if row is None:
        # Generate a new keypair and persist it
        priv_pem, pub_pem = generate_keypair()
        bundle = encrypt_for_tenant(priv_pem, org_id=org_id)
        row = TenantKey(
            organization_id=_uuid.UUID(org_id),
            purpose=PURPOSE,
            encrypted_key=bundle,
            metadata={"bundle_signing_pub_pem": pub_pem.decode()},
        )
        session.add(row)
        await session.flush()
        log.info("bundle_signing.keypair_created", org_id=org_id)
        return priv_pem, pub_pem

    # Decrypt private key and extract public key from metadata
    priv_pem = decrypt_for_tenant(row.encrypted_key, org_id=org_id)
    pub_pem = (row.metadata or {}).get("bundle_signing_pub_pem", "").encode()
    if not pub_pem:
        # Regenerate public key from private key (recovery path)
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key, Encoding, PublicFormat
        )
        priv_obj = load_pem_private_key(priv_pem, password=None)
        pub_pem = priv_obj.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        )
        row.metadata = {**(row.metadata or {}), "bundle_signing_pub_pem": pub_pem.decode()}
        await session.flush()
    return priv_pem, pub_pem
