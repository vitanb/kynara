"""Field-level encryption for sensitive database values (tokens, secrets, webhook URLs).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
The key is derived from ENCRYPTION_KEY env var.

Usage::

    from app.core.encryption import encrypt, decrypt

    stored = encrypt("xoxb-my-slack-token")   # store this in DB
    plain  = decrypt(stored)                   # retrieve plaintext
"""
from __future__ import annotations

import base64
import hashlib
import logging

log = logging.getLogger("kynara.encryption")

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    try:
        from cryptography.fernet import Fernet
        from app.core.config import get_settings
        raw_key = get_settings().encryption_key
        if not raw_key:
            log.warning("ENCRYPTION_KEY not set — field encryption disabled (plaintext storage)")
            return None
        # Derive a 32-byte key from the raw value and base64url-encode for Fernet
        derived = hashlib.sha256(raw_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        _fernet = Fernet(fernet_key)
    except ImportError:
        log.warning("cryptography package not installed — field encryption disabled")
        _fernet = None
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string value for database storage. Returns the ciphertext string."""
    f = _get_fernet()
    if f is None:
        return plaintext  # fallback: store plaintext if encryption unavailable
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored ciphertext value. Returns plaintext."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    if f is None:
        return ciphertext  # fallback: assume already plaintext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Value may have been stored unencrypted (migration scenario)
        log.debug("Fernet decrypt failed — returning value as-is")
        return ciphertext
