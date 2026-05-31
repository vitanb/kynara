"""JWT access tokens + opaque rotating refresh tokens."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings


@dataclass(frozen=True)
class AccessTokenClaims:
    sub: str         # user id (uuid)
    org: str         # active organization id (uuid)
    seat: str        # seat role
    scopes: tuple[str, ...]
    jti: str
    iat: int
    exp: int
    amr: tuple[str, ...]
    is_superadmin: bool = False


def mint_access_token(
    *,
    user_id: str,
    org_id: str,
    seat_role: str,
    scopes: list[str],
    amr: list[str],
    is_superadmin: bool = False,
) -> str:
    s = get_settings()
    now = int(datetime.now(tz=timezone.utc).timestamp())
    payload: dict[str, Any] = {
        "sub": user_id,
        "org": org_id,
        "seat": seat_role,
        "scopes": scopes,
        "amr": amr,
        "iat": now,
        "exp": now + s.jwt_access_ttl_seconds,
        "jti": uuid.uuid4().hex,
        "iss": "kynara",
        "aud": "kynara-api",
        "sadm": is_superadmin,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> AccessTokenClaims:
    s = get_settings()
    data = jwt.decode(
        token,
        s.jwt_secret,
        algorithms=["HS256"],
        audience="kynara-api",
        issuer="kynara",
    )
    return AccessTokenClaims(
        sub=data["sub"],
        org=data["org"],
        seat=data["seat"],
        scopes=tuple(data.get("scopes", [])),
        jti=data["jti"],
        iat=data["iat"],
        exp=data["exp"],
        amr=tuple(data.get("amr", [])),
        is_superadmin=bool(data.get("sadm", False)),
    )


# ------------------------------------------------------------ refresh tokens --
def _refresh_hmac_key() -> bytes:
    """Derive a stable HMAC key from the JWT secret for refresh token hashing.

    Using HMAC-SHA256 instead of plain SHA-256 means that an attacker who
    obtains the hashed token values from the database cannot brute-force them
    without also knowing the server secret (F-05 remediation).
    """
    secret = get_settings().jwt_secret
    # Domain-separate the key so it can't be reused for JWT verification
    return hashlib.sha256(f"refresh-token-hmac:{secret}".encode()).digest()


def mint_refresh_token() -> tuple[str, str]:
    """Return (clear_text_token, HMAC-SHA256 hash for DB storage)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    """Compute HMAC-SHA256(token, derived_key) as a hex string."""
    return hmac.new(_refresh_hmac_key(), raw.encode(), hashlib.sha256).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(
        seconds=get_settings().jwt_refresh_ttl_seconds
    )


# ----------------------------------------------------------------- API keys --
def _api_key_hmac_key() -> bytes:
    """Derive a stable HMAC key for API key hashing.

    Domain-separated from the refresh-token key so the two cannot be
    cross-used even if an attacker obtains one derived key.

    NOTE: Changing jwt_secret invalidates all existing hashed API keys.
    Existing keys must be rotated when the secret changes.
    """
    secret = get_settings().jwt_secret
    return hashlib.sha256(f"api-key-hmac:{secret}".encode()).digest()


def hash_api_key(raw: str) -> str:
    """Compute HMAC-SHA256(api_key, derived_key) as a hex string.

    Store this hash; never the clear-text key.  Consistent with the
    refresh-token approach so both token types resist offline brute-force
    even if the api_keys table is leaked without the server secret.

    MIGRATION NOTE: Existing rows hashed with plain SHA-256 will not match
    this new scheme.  Run a key-rotation campaign (revoke + re-issue) after
    deploying this change.
    """
    return hmac.new(_api_key_hmac_key(), raw.encode(), hashlib.sha256).hexdigest()
