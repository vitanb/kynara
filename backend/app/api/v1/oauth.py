"""OAuth 2.0 Authorization Server for the Kynara MCP connector.

Implements Authorization Code flow + PKCE (S256) as required by the
Anthropic Connectors Directory.  No client_secret needed for public clients
(Claude is a public client).

Endpoints
---------
GET  /oauth/authorize                                    Show consent page (redirect to /oauth/consent)
POST /oauth/authorize                                    Accept consent, issue auth code, redirect
POST /oauth/token                                        Exchange auth code for access token
GET  /oauth/userinfo                                     Return basic claims for the authed user
GET  /oauth/register                                     RFC 7591 endpoint probe (returns 200)
POST /oauth/register                                     RFC 7591 dynamic client registration
GET  /.well-known/oauth-authorization-server             RFC 8414 AS metadata
GET  /.well-known/oauth-protected-resource               RFC 9728 resource metadata (root form)
GET  /.well-known/oauth-protected-resource/{path:path}   RFC 9728 resource metadata (path form)
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.auth.tokens import mint_access_token
from app.db.session import SessionLocal
from app.models import OAuthClient, OAuthCode, OrgMembership, User

import logging
log = logging.getLogger("kynara.oauth")

router = APIRouter(tags=["oauth"])

_CODE_TTL_SECONDS  = 120   # auth codes expire in 2 minutes
_TOKEN_TTL_SECONDS = 3600  # access tokens expire in 1 hour


async def _db():
    async with SessionLocal() as s:
        yield s


# -- RFC 8414 AS metadata -----------------------------------------------------

@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_metadata(request: Request):
    base = str(request.base_url).rstrip("/")
    log.info("GET /.well-known/oauth-authorization-server — base=%s headers=%s", base, dict(request.headers))
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint":   f"{base}/oauth/authorize",
        "token_endpoint":           f"{base}/oauth/token",
        "userinfo_endpoint":        f"{base}/oauth/userinfo",
        "registration_endpoint":    f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported":    ["authorization_code"],
        "code_challenge_methods_supported":        ["S256"],
        "token_endpoint_auth_methods_supported":   ["none"],
        "scopes_supported": ["read", "write"],
    })


# -- RFC 9728 protected resource metadata -------------------------------------

def _protected_resource_response(base: str) -> JSONResponse:
    return JSONResponse({
        "resource":                 base,
        "authorization_servers":    [base],
        "bearer_methods_supported": ["header"],
        "resource_documentation":   f"{base}/docs",
    })


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def oauth_protected_resource(request: Request):
    """RFC 9728 root form."""
    base = str(request.base_url).rstrip("/")
    return _protected_resource_response(base)


@router.get("/.well-known/oauth-protected-resource/{path:path}", include_in_schema=False)
async def oauth_protected_resource_path(request: Request, path: str):
    """RFC 9728 path-appended form.

    When the protected resource URL has a path component (e.g. /mcp/v1/sse),
    RFC 9728 §3.1 says clients MUST also try:
      /.well-known/oauth-protected-resource/mcp/v1/sse
    Return the same metadata as the root form.
    """
    base = str(request.base_url).rstrip("/")
    return _protected_resource_response(base)


# -- RFC 7591 dynamic client registration -------------------------------------

@router.get("/oauth/register", include_in_schema=False)
async def register_client_get(request: Request, db: AsyncSession = Depends(_db)):
    """GET /oauth/register — Claude.ai uses this to retrieve an existing client
    registration before starting the authorization flow.  We return the
    pre-seeded 'claude-connector' record so Claude gets a valid client_id and
    can proceed to GET /oauth/authorize.

    If somehow the seeded client is missing, return 404 so the caller can POST
    to create a fresh registration.
    """
    log.info("GET /oauth/register — headers: %s", dict(request.headers))
    client = await db.scalar(
        select(OAuthClient).where(
            OAuthClient.client_id == "claude-connector",
            OAuthClient.is_active.is_(True),
        )
    )
    if not client:
        log.warning("GET /oauth/register: claude-connector not found in DB — returning 404")
        raise HTTPException(status_code=404, detail="client not found")

    redirect_uris = [u.strip() for u in client.redirect_uris.split(",") if u.strip()]
    log.info("GET /oauth/register → 200 client_id=claude-connector redirect_uris=%s", redirect_uris)
    return JSONResponse({
        "client_id":                  client.client_id,
        "client_name":                client.client_name,
        "redirect_uris":              redirect_uris,
        "grant_types":                ["authorization_code"],
        "response_types":             ["code"],
        "token_endpoint_auth_method": "none",
    })


@router.post("/oauth/register", include_in_schema=False)
async def register_client(request: Request, db: AsyncSession = Depends(_db)):
    """RFC 7591 Dynamic Client Registration.

    Claude self-registers before initiating the OAuth flow when the server
    advertises a registration_endpoint.  We accept any public client (PKCE is
    the security mechanism, not the redirect_uri).
    """
    body = await request.json()
    log.info("POST /oauth/register body=%s headers=%s", body, dict(request.headers))
    client_id: str = body.get("client_id") or f"dyn-{secrets.token_urlsafe(16)}"
    redirect_uris: list[str] = body.get("redirect_uris", [])
    client_name: str = body.get("client_name", "Dynamic Client")

    existing = await db.scalar(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    if existing:
        # Idempotent — update URIs in case they changed
        stored = set(existing.redirect_uris.split(",")) if existing.redirect_uris else set()
        merged = stored | set(redirect_uris)
        existing.redirect_uris = ",".join(u for u in merged if u)
        await db.commit()
    else:
        db.add(OAuthClient(
            client_id=client_id,
            client_name=client_name,
            redirect_uris=",".join(redirect_uris),
            allowed_scopes="read write",
            is_public=True,
            is_active=True,
        ))
        await db.commit()

    return JSONResponse(status_code=201, content={
        "client_id":                  client_id,
        "client_name":                client_name,
        "redirect_uris":              redirect_uris,
        "grant_types":                ["authorization_code"],
        "response_types":             ["code"],
        "token_endpoint_auth_method": "none",
    })


# -- GET /oauth/authorize -----------------------------------------------------

@router.get("/oauth/authorize")
async def authorize_get(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    scope: str = Query("read"),
    state: str = Query(""),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query("S256"),
    db: AsyncSession = Depends(_db),
):
    """Validate params and serve the consent/login page."""
    log.info(
        "GET /oauth/authorize client_id=%s redirect_uri=%s scope=%s headers=%s",
        client_id, redirect_uri, scope, dict(request.headers),
    )
    await _validate_client(client_id, redirect_uri, db)

    if response_type != "code":
        raise HTTPException(400, "Only response_type=code is supported")
    if code_challenge_method != "S256":
        raise HTTPException(400, "Only code_challenge_method=S256 is supported")

    params = urllib.parse.urlencode({
        "client_id":             client_id,
        "redirect_uri":          redirect_uri,
        "scope":                 scope,
        "state":                 state,
        "code_challenge":        code_challenge,
        "code_challenge_method": code_challenge_method,
    })
    return RedirectResponse(url=f"/oauth/consent?{params}", status_code=302)


# -- POST /oauth/authorize ----------------------------------------------------

@router.post("/oauth/authorize")
async def authorize_post(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    scope: str = Form("read"),
    state: str = Form(""),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    db: AsyncSession = Depends(_db),
    principal: Principal = Depends(get_principal),
):
    """User approved — mint an auth code and redirect."""
    await _validate_client(client_id, redirect_uri, db)

    code_str = secrets.token_urlsafe(32)
    db.add(OAuthCode(
        code=code_str,
        client_id=client_id,
        user_id=principal.user_id,
        org_id=principal.org_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=_CODE_TTL_SECONDS),
    ))
    await db.commit()

    qs = urllib.parse.urlencode({"code": code_str, "state": state})
    callback_url = f"{redirect_uri}?{qs}"

    # The frontend POSTs via fetch() — fetch with redirect:"manual" cannot
    # read the Location header from a 302 (opaque redirect), so the browser
    # would navigate nowhere.  Return JSON 200 instead; the frontend reads
    # redirect_uri and does window.location.href = ... manually.
    # Direct browser form submissions (non-XHR) will also work because they
    # look for res.ok + data.redirect_uri in the existing frontend code.
    return JSONResponse({"redirect_uri": callback_url})


# -- POST /oauth/token --------------------------------------------------------

@router.post("/oauth/token")
async def token_endpoint(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: str = Form(...),
    db: AsyncSession = Depends(_db),
):
    """Exchange authorization code for an access token."""
    if grant_type != "authorization_code":
        raise HTTPException(400, "unsupported_grant_type")

    row: OAuthCode | None = await db.scalar(
        select(OAuthCode).where(OAuthCode.code == code)
    )
    if not row:
        raise HTTPException(400, "invalid_grant: code not found")
    if row.used:
        raise HTTPException(400, "invalid_grant: code already used")
    if row.client_id != client_id:
        raise HTTPException(400, "invalid_grant: client_id mismatch")
    if row.redirect_uri != redirect_uri:
        raise HTTPException(400, "invalid_grant: redirect_uri mismatch")
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, "invalid_grant: code expired")

    # Verify PKCE S256
    digest = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    if digest != row.code_challenge:
        raise HTTPException(400, "invalid_grant: code_verifier mismatch")

    row.used = True
    await db.commit()

    user = await db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "invalid_grant: user not found or inactive")

    membership = await db.scalar(
        select(OrgMembership).where(
            OrgMembership.user_id == row.user_id,
            OrgMembership.organization_id == row.org_id,
        )
    )
    if not membership:
        raise HTTPException(400, "invalid_grant: org membership not found")

    granted_scopes = [s.strip() for s in row.scope.split() if s.strip()]
    internal_scopes: list[str] = []
    if "read" in granted_scopes:
        internal_scopes += ["agents:read", "audit:read", "approvals:read", "roles:read"]
    if "write" in granted_scopes:
        internal_scopes += ["approvals:write", "agents:write", "roles:write"]

    access_token = mint_access_token(
        user_id=str(row.user_id),
        org_id=str(row.org_id),
        seat_role=membership.seat_role,
        scopes=internal_scopes,
        amr=["oauth2"],
    )

    return JSONResponse({
        "access_token": access_token,
        "token_type":   "bearer",
        "expires_in":   _TOKEN_TTL_SECONDS,
        "scope":        row.scope,
    })


# -- GET /oauth/userinfo ------------------------------------------------------

@router.get("/oauth/userinfo")
async def userinfo(
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(_db),
):
    user = await db.get(User, principal.user_id)
    return JSONResponse({
        "sub":    str(principal.user_id),
        "org_id": str(principal.org_id),
        "email":  user.email if user else None,
        "name":   user.display_name if user else None,
        "role":   principal.seat_role,
    })


# -- helpers ------------------------------------------------------------------

async def _validate_client(
    client_id: str, redirect_uri: str, db: AsyncSession
) -> OAuthClient:
    client: OAuthClient | None = await db.scalar(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.is_active.is_(True),
        )
    )
    if not client:
        raise HTTPException(400, "invalid_client")

    allowed = [u.strip() for u in client.redirect_uris.split(",") if u.strip()]

    # For public clients (no client_secret), PKCE is the security mechanism.
    # claude-connector and dyn-* clients (dynamically registered) are trusted:
    # accept any redirect_uri so Cowork desktop, Claude.ai web, and future
    # Claude surfaces can complete the flow without needing exact URI prediction.
    is_trusted = client_id == "claude-connector" or client_id.startswith("dyn-")
    if allowed and redirect_uri not in allowed and not is_trusted:
        raise HTTPException(400, "redirect_uri not allowed for this client")

    return client
