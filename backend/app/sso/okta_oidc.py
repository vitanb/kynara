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
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.ssrf import assert_safe_url


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
    """Fetch the OIDC discovery document with SSRF protection.

    The issuer URL comes from admin-configured SSO connections, but we still
    validate it to prevent SSRF in case of a misconfiguration or a compromised
    admin account targeting internal metadata endpoints.
    """
    discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        assert_safe_url(discovery_url, scheme_whitelist={"https"})
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"OIDC issuer URL is not allowed: {exc}",
        ) from exc
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(discovery_url)
        r.raise_for_status()
        return r.json()


# ── Generic (connection-aware) helpers ─────────────────────────────────────

async def start_flow_with_config(
    cfg: OidcConfig,
    *,
    state_override: str | None = None,
) -> tuple[str, dict]:
    """Return (redirect_url, state_bundle). Accepts explicit IdP credentials.

    ``state_override`` lets the caller supply the OIDC ``state`` value (e.g. a
    Redis key) so that Auth0/any IdP echoes it back verbatim in the callback,
    making it trivial to look up the stored bundle without a separate parameter.
    """
    meta = await _fetch_well_known(cfg.issuer)
    # Use caller-supplied state (the Redis key) so the IdP echoes it back in
    # the callback query string as ?state=<key>. Falls back to a random value
    # for the legacy Okta routes that manage state separately.
    state = state_override or secrets.token_urlsafe(32)
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
        # Always prompt for credentials — prevents Auth0 from silently reusing
        # a browser session from a previously logged-in user, which would cause
        # the wrong user's claims to come back in the callback.
        "prompt": "login",
    }
    url = meta["authorization_endpoint"] + "?" + "&".join(
        f"{k}={httpx.QueryParams(params)[k]}" for k in params
    )
    # NOTE: client_secret is intentionally NOT stored in the state bundle.
    # It is looked up from the database by connection_id in the callback so
    # that a Redis compromise never exposes OAuth client credentials.
    return url, {
        "state": state, "nonce": nonce, "verifier": verifier,
        "issuer": cfg.issuer, "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        # client_secret omitted — caller must inject it at token-exchange time
    }


async def complete_flow_with_config(
    code: str,
    state_bundle: dict,
    *,
    client_secret: str | None = None,
) -> dict:
    """Exchange code → validated id_token claims.

    Args:
        code: The authorization code from the IdP callback.
        state_bundle: The bundle stored in Redis (must contain issuer, client_id,
            redirect_uri, verifier, nonce).  It must NOT contain client_secret —
            that is passed explicitly via ``client_secret`` so it never touches Redis.
        client_secret: The OAuth client secret.  Callers that previously relied on
            ``state_bundle["client_secret"]`` must migrate to pass it here.
    """
    meta = await _fetch_well_known(state_bundle["issuer"])
    # Prefer explicit parameter; fall back to bundle key for backward compat
    # (legacy Okta routes that haven't been updated yet).
    resolved_secret = client_secret or state_bundle.get("client_secret", "")

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
                "client_secret": resolved_secret,
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
