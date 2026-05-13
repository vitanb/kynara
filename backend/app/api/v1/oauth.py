"""OAuth 2.0 Authorization Server for the Kynara MCP connector.

Implements Authorization Code flow + PKCE (S256) as required by the
Anthropic Connectors Directory.  No client_secret needed for public clients
(Claude is a public client).

Endpoints
---------
GET  /oauth/authorize       Show login/consent page (or redirect if already authed)
POST /oauth/authorize       Accept user consent, issue auth code, redirect
POST /oauth/token           Exchange auth code for access token
GET  /oauth/userinfo        Return basic claims for the authed user
GET  /.well-known/oauth-authorization-server  RFC 8414 metadata

Flow
----
1. Claude opens  GET /oauth/authorize?client_id=claude-connector&redirect_uri=...
                 &response_type=code&scope=read+write&state=...
                 &code_challenge=<S256>&code_challenge_method=S256
2. User is shown a Kynara login page (served from frontend at /oauth/consent).
   If already authenticated (Bearer token in cookie / header), skip login.
3. User approves -> POST /oauth/authorize -> 302 redirect_uri?code=...&state=...
4. Claude exchanges code:  POST /oauth/token
   body: grant_type=authorization_code&code=...&redirect_uri=...
         &code_verifier=...&client_id=claude-connector
5. Server returns:  {"access_token": "<jwt>", "token_type": "bearer",
                     "expires_in": 3600, "scope": "read write"}
6. Claude uses access_token as Bearer on /mcp/v1/sse requests.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.auth.tokens import mint_access_token
from app.db.session import SessionLocal
from app.models import OAuthClient, OAuthCode, OrgMembership, User

router = APIRouter(tags=["oauth"])

_CODE_TTL_SECONDS = 120   # auth codes expire in 2 minutes
_TOKEN_TTL_SECONDS = 3600  # access tokens expire in 1 hour


async def _db():
    async with SessionLocal() as s:
        yield s


# -- RFC 8414 metadata --------------------------------------------------------

@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_metadata(request: Request):
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "userinfo_endpoint": f"{base}/oauth/userinfo",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["read", "write"],
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
    await _validate_client(client_id, redirect_uri, db)

    if response_type != "code":
        raise HTTPException(400, "Only response_type=code is supported")
    if code_challenge_method != "S256":
        raise HTTPException(400, "Only code_challenge_method=S256 is supported")

    # Build a URL that the frontend consent page will POST back to
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    })

    # Redirect to the frontend consent page
    return RedirectResponse(
        url=f"/oauth/consent?{params}",
        status_code=302,
    )


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
    """User approved -- mint an auth code and redirect."""
    client = await _validate_client(client_id, redirect_uri, db)

    code_str = secrets.token_urlsafe(32)
    code = OAuthCode(
        code=code_str,
        client_id=client_id,
        user_id=principal.user_id,
        org_id=principal.org_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=_CODE_TTL_SECONDS),
    )
    db.add(code)
    await db.commit()

    qs = urllib.parse.urlencode({"code": code_str, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{qs}", status_code=302)


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

    # Mark code as used (one-time)
    row.used = True
    await db.commit()

    # Load user + membership to build Principal-equivalent claims
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

    # Derive scopes from what the client was granted (map "read"/"write" to
    # internal scope strings so the Principal looks normal to downstream code)
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
        "token_type": "bearer",
        "expires_in": _TOKEN_TTL_SECONDS,
        "scope": row.scope,
    })


# -- GET /oauth/userinfo ------------------------------------------------------

@router.get("/oauth/userinfo")
async def userinfo(
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(_db),
):
    user = await db.get(User, principal.user_id)
    return JSONResponse({
        "sub": principal.user_id,
        "org_id": principal.org_id,
        "email": user.email if user else None,
        "name": user.display_name if user else None,
        "role": principal.seat_role,
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

    allowed = [u.strip() for u in client.redirect_uris.split(",")]
    if redirect_uri not in allowed:
        raise HTTPException(400, "redirect_uri not allowed for this client")

    return client
