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
        resp = self._client.encrypt(
            request={
                "name": key_id or self._key_name,
                "plaintext": plaintext,
                "additional_authenticated_data": aad,
            }
        )
        log.debug("kms.gcp.generate_data_key", key_name=key_id or self._key_name)
        # Pack the GCP ciphertext alongside the AAD so decrypt can reconstruct it.
        import struct
        aad_len = struct.pack(">I", len(aad))
        ciphertext_blob = aad_len + aad + resp.ciphertext
        return DataKey(plaintext=plaintext, ciphertext_blob=ciphertext_blob)

    def decrypt(self, ciphertext_blob: bytes, *, encryption_context: dict[str, str]) -> bytes:
        """Unwrap a GCP KMS-wrapped data key."""
        import json
        import struct
        from google.cloud import kms as gcp_kms  # type: ignore

        aad_len = struct.unpack(">I", ciphertext_blob[:4])[0]
        aad = ciphertext_blob[4: 4 + aad_len]
        gcp_ciphertext = ciphertext_blob[4 + aad_len:]
        resp = self._client.decrypt(
            request={
                "name": self._key_name,
                "ciphertext": gcp_ciphertext,
                "additional_authenticated_data": aad,
            }
        )
        log.debug("kms.gcp.decrypt")
        return resp.plaintext


class AzureKmsBackend:
    """Azure Key Vault backend using azure-keyvault-keys + azure-identity.

    The managed identity / service principal must have Key Vault access policy
    permissions: get, wrapKey, unwrapKey  (or Key Vault Crypto User RBAC role).

    We use RSA-OAEP-256 wrap/unwrap semantics: generate a random AES-256 data
    key locally, then wrap it with the vault key using wrapKey.  This mirrors
    the AWS/GCP "generate data key" pattern without requiring a symmetric key
    in Azure (RSA keys are more common in Key Vault BYOK scenarios).
    """

    def __init__(self, vault_url: str | None = None, key_name: str | None = None):
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm  # type: ignore
            from azure.keyvault.keys import KeyClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "azure-keyvault-keys and azure-identity are required for the Azure KMS backend. "
                "Add 'azure-keyvault-keys>=4.9' and 'azure-identity>=1.16' to pyproject.toml."
            ) from exc
        self._vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URL", "")
        self._key_name = key_name or os.environ.get("AZURE_KEY_NAME", "")
        if not self._vault_url or not self._key_name:
            raise RuntimeError(
                "AZURE_KEYVAULT_URL and AZURE_KEY_NAME must both be set for the Azure KMS backend."
            )
        from azure.identity import DefaultAzureCredential  # type: ignore
        from azure.keyvault.keys import KeyClient  # type: ignore
        self._credential = DefaultAzureCredential()
        self._key_client = KeyClient(vault_url=self._vault_url, credential=self._credential)

    def _crypto_client(self, key_id: str):
        from azure.keyvault.keys.crypto import CryptographyClient  # type: ignore
        key = self._key_client.get_key(key_id or self._key_name)
        return CryptographyClient(key, credential=self._credential)

    def generate_data_key(self, key_id: str, *, encryption_context: dict[str, str]) -> DataKey:
        """Generate a random AES-256 data key and wrap it using the vault key."""
        import json
        from azure.keyvault.keys.crypto import KeyWrapAlgorithm  # type: ignore

        plaintext = secrets.token_bytes(32)
        client = self._crypto_client(key_id)
        result = client.wrap_key(KeyWrapAlgorithm.rsa_oaep_256, plaintext)
        # Embed the encryption context in the blob so decrypt can verify it.
        ctx_bytes = json.dumps(encryption_context, sort_keys=True).encode()
        import struct
        ctx_len = struct.pack(">I", len(ctx_bytes))
        ciphertext_blob = ctx_len + ctx_bytes + result.encrypted_key
        log.debug("kms.azure.generate_data_key", key_name=key_id or self._key_name)
        return DataKey(plaintext=plaintext, ciphertext_blob=ciphertext_blob)

    def decrypt(self, ciphertext_blob: bytes, *, encryption_context: dict[str, str]) -> bytes:
        """Unwrap an Azure Key Vault-wrapped data key."""
        import json
        import struct
        from azure.keyvault.keys.crypto import KeyWrapAlgorithm  # type: ignore

        ctx_len = struct.unpack(">I", ciphertext_blob[:4])[0]
        ctx_bytes = ciphertext_blob[4: 4 + ctx_len]
        wrapped_key = ciphertext_blob[4 + ctx_len:]
        stored_ctx = json.loads(ctx_bytes)
        if stored_ctx != encryption_context:
            raise PermissionError("encryption_context mismatch")
        client = self._crypto_client(self._key_name)
        result = client.unwrap_key(KeyWrapAlgorithm.rsa_oaep_256, wrapped_key)
        log.debug("kms.azure.decrypt")
        return result.key


_backend: KmsBackend | None = None


def get_backend() -> KmsBackend:
    global _backend
    if _backend is None:
        backend_name = os.environ.get("KYNARA_KMS_BACKEND", "local")
        if backend_name == "local":
            seed = os.environ.get("KYNARA_KMS_LOCAL_KEY", "")
            if not seed:
                seed = secrets.token_hex(32)
                log.warning(
                    "kms.using_ephemeral_local_key — set KYNARA_KMS_LOCAL_KEY for persistence"
                )
            _backend = LocalKmsBackend(bytes.fromhex(seed))
        elif backend_name == "aws":
            region = os.environ.get("AWS_REGION")
            _backend = AwsKmsBackend(region=region)
            log.info("kms.backend_aws", region=region)
        elif backend_name == "gcp":
            key_name = os.environ.get("GCP_KMS_KEY_NAME")
            _backend = GcpKmsBackend(key_name=key_name)
            log.info("kms.backend_gcp", key_name=key_name)
        elif backend_name == "azure":
            vault_url = os.environ.get("AZURE_KEYVAULT_URL")
            key_name = os.environ.get("AZURE_KEY_NAME")
            _backend = AzureKmsBackend(vault_url=vault_url, key_name=key_name)
            log.info("kms.backend_azure", vault_url=vault_url, key_name=key_name)
        else:
            raise NotImplementedError(
                f"Unknown KMS backend: {backend_name!r}. "
                "Valid values: 'local', 'aws', 'gcp', 'azure'."
            )
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
