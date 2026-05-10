"""Per-tenant envelope encryption with KMS.

The platform provides AES-256-GCM "data keys" derived from a per-tenant KMS
key. Tenants on Enterprise plans can elect BYOK (Bring-Your-Own-Key): they
configure an AWS KMS key in their account and grant Kynara's worker role
``kms:GenerateDataKey`` and ``kms:Decrypt`` on it. We never see the master key.

This module is the abstraction layer between the application and KMS. It is
deliberately *not* coupled to AWS so the same interface can wrap GCP KMS,
Azure Key Vault, or HashiCorp Vault Transit on customer demand.

Backend selection (KYNARA_KMS_BACKEND env var):
  - "local"  — dev/CI XOR backend (default). Set KYNARA_KMS_LOCAL_KEY to a 64-char hex string.
  - "aws"    — production AWS KMS via boto3. Requires:
                 AWS_KMS_KEY_ID       — default key ARN/alias for platform-managed keys
                 AWS_REGION           — e.g. us-east-1 (or use standard boto3 env vars)
                 Standard boto3 credential chain (IAM role, env vars, ~/.aws/credentials)
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("kynara.kms")


@dataclass
class DataKey:
    plaintext: bytes      # 32 bytes for AES-256
    ciphertext_blob: bytes  # opaque KMS-encrypted bytes — store this with the data


class KmsBackend(Protocol):
    def generate_data_key(self, key_id: str, *, encryption_context: dict[str, str]) -> DataKey: ...
    def decrypt(self, ciphertext_blob: bytes, *, encryption_context: dict[str, str]) -> bytes: ...


class LocalKmsBackend:
    """Development/CI backend. NEVER use in production."""

    def __init__(self, master_key: bytes):
        if len(master_key) != 32:
            raise ValueError("master_key must be 32 bytes")
        self._master = master_key

    def generate_data_key(self, key_id: str, *, encryption_context: dict[str, str]) -> DataKey:
        plaintext = secrets.token_bytes(32)
        # In real KMS the ciphertext_blob is opaque — for the local backend we
        # XOR with the master and concatenate the encryption context.
        ct = bytes(a ^ b for a, b in zip(plaintext, self._master))
        ctx = base64.urlsafe_b64encode(repr(encryption_context).encode())
        return DataKey(plaintext=plaintext, ciphertext_blob=ct + b"|" + ctx)

    def decrypt(self, ciphertext_blob: bytes, *, encryption_context: dict[str, str]) -> bytes:
        ct, ctx_b = ciphertext_blob.split(b"|", 1)
        ctx = base64.urlsafe_b64decode(ctx_b)
        if ctx != repr(encryption_context).encode():
            raise PermissionError("encryption_context mismatch")
        return bytes(a ^ b for a, b in zip(ct, self._master))


class AwsKmsBackend:
    """Production AWS KMS backend using boto3.

    The Kynara worker IAM role must have:
        kms:GenerateDataKey
        kms:Decrypt
    on the tenant's key (BYOK) or the platform default key.

    boto3 uses the standard credential chain:
        1. Environment vars (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
        2. IAM instance / task role (recommended for Railway / ECS / EKS)
        3. ~/.aws/credentials
    """

    def __init__(self, region: str | None = None):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is required for the AWS KMS backend. "
                "Add 'boto3>=1.34' to pyproject.toml dependencies."
            ) from exc
        self._client = boto3.client("kms", region_name=region or os.environ.get("AWS_REGION"))

    def generate_data_key(self, key_id: str, *, encryption_context: dict[str, str]) -> DataKey:
        """Ask AWS KMS to generate a 256-bit data key envelope-encrypted under key_id."""
        log.debug("kms.generate_data_key", extra={"key_id": key_id})
        resp = self._client.generate_data_key(
            KeyId=key_id,
            KeySpec="AES_256",
            EncryptionContext=encryption_context,
        )
        return DataKey(
            plaintext=resp["Plaintext"],           # 32 raw bytes — use then zero-out
            ciphertext_blob=resp["CiphertextBlob"],  # opaque blob — store alongside ciphertext
        )

    def decrypt(self, ciphertext_blob: bytes, *, encryption_context: dict[str, str]) -> bytes:
        """Decrypt a KMS-wrapped data key back to plaintext bytes."""
        log.debug("kms.decrypt")
        resp = self._client.decrypt(
            CiphertextBlob=ciphertext_blob,
            EncryptionContext=encryption_context,
        )
        return resp["Plaintext"]


_backend: KmsBackend | None = None


def get_backend() -> KmsBackend:
    global _backend
    if _backend is None:
        backend_name = os.environ.get("KYNARA_KMS_BACKEND", "local")
        if backend_name == "local":
            seed = os.environ.get("KYNARA_KMS_LOCAL_KEY", "")
            if not seed:
                # Generate a random key for dev — log a warning so it's visible.
                seed = secrets.token_hex(32)
                log.warning(
                    "kms.using_ephemeral_local_key — set KYNARA_KMS_LOCAL_KEY for persistence"
                )
            _backend = LocalKmsBackend(bytes.fromhex(seed))
        elif backend_name == "aws":
            region = os.environ.get("AWS_REGION")
            _backend = AwsKmsBackend(region=region)
            log.info("kms.backend_aws", region=region)
        else:
            raise NotImplementedError(f"Unknown KMS backend: {backend_name!r}. Use 'local' or 'aws'.")
    return _backend


def encrypt_for_tenant(plaintext: bytes, *, org_id: str, kms_key_id: str | None = None) -> dict:
    """Generate a data key, encrypt plaintext under it, return the bundle."""
    backend = get_backend()
    key_id = kms_key_id or f"alias/kynara-tenant-{org_id}"
    dk = backend.generate_data_key(key_id, encryption_context={"org_id": org_id})

    # AES-256-GCM
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    aes = AESGCM(dk.plaintext)
    ct = aes.encrypt(nonce, plaintext, associated_data=org_id.encode())
    return {
        "v": 1,
        "kms_key_id": key_id,
        "ciphertext_blob": base64.b64encode(dk.ciphertext_blob).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ct).decode(),
    }


def decrypt_for_tenant(bundle: dict, *, org_id: str) -> bytes:
    backend = get_backend()
    cb = base64.b64decode(bundle["ciphertext_blob"])
    nonce = base64.b64decode(bundle["nonce"])
    ct = base64.b64decode(bundle["ciphertext"])
    pt_key = backend.decrypt(cb, encryption_context={"org_id": org_id})

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aes = AESGCM(pt_key)
    return aes.decrypt(nonce, ct, associated_data=org_id.encode())
