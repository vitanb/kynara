"""Per-tenant envelope encryption with KMS.

The platform provides AES-256-GCM "data keys" derived from a per-tenant KMS
key. Tenants on Enterprise plans can elect BYOK (Bring-Your-Own-Key): they
configure a KMS key in their account and grant Kynara's worker role the
necessary permissions. We never see the master key.

This module is the abstraction layer between the application and KMS.

Backend selection (KYNARA_KMS_BACKEND env var):
  - "local"  — dev/CI XOR backend (default). Set KYNARA_KMS_LOCAL_KEY to a 64-char hex string.
  - "aws"    — AWS KMS via boto3. Requires:
                 AWS_KMS_KEY_ID, AWS_REGION
                 IAM permissions: kms:GenerateDataKey, kms:Decrypt
  - "gcp"    — GCP Cloud KMS via google-cloud-kms. Requires:
                 GCP_KMS_KEY_NAME     — full resource name:
                   projects/{p}/locations/{l}/keyRings/{r}/cryptoKeys/{k}
                 GOOGLE_APPLICATION_CREDENTIALS or Workload Identity
                 IAM role: roles/cloudkms.cryptoKeyEncrypterDecrypter
  - "azure"  — Azure Key Vault via azure-keyvault-keys. Requires:
                 AZURE_KEYVAULT_URL   — e.g. https://my-vault.vault.azure.net
                 AZURE_KEY_NAME       — name of the RSA/EC key in the vault
                 Standard Azure credential chain (DefaultAzureCredential):
                   env vars, managed identity, VS Code, Azure CLI, etc.
                 Key Vault access policy: get, wrapKey, unwrapKey
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


class GcpKmsBackend:
    """GCP Cloud KMS backend using google-cloud-kms.

    The service account / Workload Identity principal must have:
        roles/cloudkms.cryptoKeyEncrypterDecrypter
    on the key ring or individual key.

    GCP KMS does not have a GenerateDataKey primitive — we generate the
    plaintext data key locally using os.urandom and wrap it with
    ``cryptoKeyVersions.asymmetricDecrypt`` (RSA-OAEP) or the symmetric
    ``encrypt``/``decrypt`` API.  We use the symmetric CryptoKey API here
    because it mirrors the AWS KMS semantics most closely.
    """

    def __init__(self, key_name: str | None = None):
        try:
            from google.cloud import kms as gcp_kms  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-kms is required for the GCP KMS backend. "
                "Add 'google-cloud-kms>=2.21' to pyproject.toml dependencies."
            ) from exc
        self._client = gcp_kms.KeyManagementServiceClient()
        self._key_name = key_name or os.environ.get("GCP_KMS_KEY_NAME", "")
        if not self._key_name:
            raise RuntimeError(
                "GCP_KMS_KEY_NAME must be set to the full CryptoKey resource name, e.g. "
                "projects/my-project/locations/global/keyRings/my-ring/cryptoKeys/my-key"
            )

    def generate_data_key(self, key_id: str, *, encryption_context: dict[str, str]) -> DataKey:
        """Generate a random 32-byte data key and wrap it with GCP KMS encrypt."""
        import json
        from google.cloud import kms as gcp_kms  # type: ignore

        plaintext = secrets.token_bytes(32)
        # Encode the encryption context as additional authenticated data (AAD).
        aad = json.dumps(encryption_context, sort_keys=True).encode()
        r