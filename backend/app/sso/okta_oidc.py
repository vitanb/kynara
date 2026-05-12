"""OIDC integration — supports Okta, Auth0, Azure AD, Google, or any OIDC-compliant IdP.

Flow (Authorization Code + PKCE):
  1. ``start_flow_with_config`` builds the /authorize URL and a state bundle.
  2. The state bundle is persisted in Redis (TTL 10 min) under a nonce key.
  3. The IdP redirects back with an auth code.
  4. ``complete_flow_with_config`` exchanges code → id_token and validates the JWT.
  5. Caller upserts User + mints Kynara access/refresh tokens.

The legacy ``start_flow`` / ``complete_flow`` wrappers use env-var Okta credentials
so the old /auth/sso/okta/* routes keep working unchanged.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class OidcConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


async def _fetch_well_known(issuer: str) -> dict:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.json()


# ── Generic (connection-aware) helpers ─────────────────────────────────────

async def start_flow_with_config(cfg: OidcConfig) -> tuple[str, dict]:
    """Return (redirect_url, state_bundle). Accepts explicit IdP credentials."""
    meta = await _fetch_well_known(cfg.issuer)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()

    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = meta["authorization_endpoint"] + "?" + "&".join(
        f"{k}={httpx.QueryParams(params)[k]}" for k in params
    )
    return url, {
        "state": state, "nonce": nonce, "verifier": verifier,
        "issuer": cfg.issuer, "client_id": cfg.client_id,
        "client_secret": cfg.client_secret, "redirect_uri": cfg.redirect_uri,
    }


async def complete_flow_with_config(code: str, state_bundle: dict) -> dict:
    """Exchange code → validated id_token claims using credentials embedded in the state bundle."""
    meta = await _fetch_well_known(state_bundle["issuer"])

    # Use the canonical issuer from the well-known config, not the stored string.
    # Auth0 always includes a trailing slash in its issuer claim
    # (e.g. "https://tenant.auth0.com/") and PyJWT rejects a mismatch even
    # if the URLs are otherwise identical.
    canonical_issuer = meta.get("issuer", state_bundle["issuer"])

    async with httpx.AsyncClient(timeout=10.0) as c:
        tok = await c.post(
            meta["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": state_bundle["redirect_uri"],
                "client_id": state_bundle["client_id"],
                "client_secret": state_bundle["client_secret"],
                "code_verifier": state_bundle["verifier"],
            },
            headers={"Accept": "application/json"},
        )
        tok.raise_for_status()
        token_resp = tok.json()
        jwks = (await c.get(meta["jwks_uri"])).json()

    import jwt
    from jwt.algorithms import RSAAlgorithm

    id_token = token_resp["id_token"]
    header = jwt.get_unverified_header(id_token)
    matching = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
    public_key = RSAAlgorithm.from_jwk(json.dumps(matching))

    claims = jwt.decode(
        id_token,
        public_key,
        algorithms=[header["alg"]],
        audience=state_bundle["client_id"],
        issuer=canonical_issuer,
    )
    if claims.get("nonce") != state_bundle["nonce"]:
        raise PermissionError("nonce mismatch")
    return claims


# ── Legacy Okta env-var wrappers (backward compat) ─────────────────────────

async def start_flow() -> tuple[str, dict]:
    """Return (redirect_url, state_bundle). Uses env-var Okta credentials."""
    s = get_settings()
    if not (s.okta_issuer and s.okta_client_id):
        raise RuntimeError("Okta OIDC not configured — set OKTA_ISSUER, OKTA_CLIENT_ID")
    return await start_flow_with_config(
        OidcConfig(
            issuer=s.okta_issuer,
            client_id=s.okta_client_id,
            client_secret=s.okta_client_secret or "",
            redirect_uri=s.okta_redirect_uri,
        )
    )


async def complete_flow(code: str, state_bundle: dict) -> dict:
    """Exchange code → id_token claims using the bundle (which may or may not have embedded creds)."""
    # If the bundle already contains client_id/secret (generic flow), use them directly.
    if "client_id" in state_bundle and "client_secret" in state_bundle:
        return await complete_flow_with_config(code, state_bundle)

    # Fallback: reconstruct from env vars (legacy okta/* routes)
    s = get_settings()
    state_bundle = {
        **state_bundle,
        "client_id": s.okta_client_id,
        "client_secret": s.okta_client_secret or "",
        "redirect_uri": s.okta_redirect_uri,
    }
    return await complete_flow_with_config(code, state_bundle)
