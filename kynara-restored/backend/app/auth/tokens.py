"""JWT access tokens + opaque rotating refresh tokens."""
from __future__ import annotations

import hashlib
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
def mint_refresh_token() -> tuple[str, str]:
    """Return (clear_text_token, sha256_hash_for_db)."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(
        seconds=get_settings().jwt_refresh_ttl_seconds
    )
