"""Argon2id password hashing with server-side pepper.

Why argon2id + pepper:
- argon2id is the OWASP-recommended password KDF. Tuned for ~500ms on t2.large.
- A pepper (application-wide secret stored outside the DB) means a raw DB leak is
  insufficient to mount an offline cracking attack. The pepper rotates by bumping
  ``password_pepper`` in config and re-hashing on next login.
"""
from __future__ import annotations

import hmac
from hashlib import sha256

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def _peppered(password: str) -> str:
    pepper = get_settings().password_pepper.encode()
    mac = hmac.new(pepper, password.encode("utf-8"), sha256).hexdigest()
    return mac


def hash_password(password: str) -> str:
    return _hasher.hash(_peppered(password))


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _hasher.verify(stored_hash, _peppered(password))
    except VerifyMismatchError:
        return False
    return True


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def hash_token(raw: str) -> str:
    """SHA-256 hash of an opaque token (webhook secrets, API keys, etc.).
    Store the hash; never the clear-text value."""
    return sha256(raw.encode()).hexdigest()
