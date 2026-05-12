"""SSO endpoints — generic OIDC (any IdP) + legacy Okta routes + SAML."""
from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("sso.api")

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_auth
from app.auth.tokens import (
    mint_access_token,
    mint_refresh_token,
    refresh_token_expiry,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import OrgMembership, RefreshSession, SsoConnection, User
from app.sso import okta_oidc, saml
from app.sso.okta_oidc import OidcConfig

router = APIRouter(prefix="/auth/sso", tags=["sso"])


async def _session():
    async with SessionLocal() as s:
        yield s


async def _redis():
    return redis_async.from_url(str(get_settings().redis_url), decode_responses=True)


# ------------------------------------------------------------------- OIDC ----
@router.get("/okta/start")
async def okta_start():
    url, state = await okta_oidc.start_flow()
    r = await _redis()
    key = f"ssos:{secrets.token_urlsafe(16)}"
    await r.setex(key, 600, json.dumps(state))
    return {"redirect_url": url, "state_key": key}


@router.get("/okta/callback")
async def okta_callback(
    code: str, state_key: str, request: Request, session: AsyncSession = Depends(_session)
):
    r = await _redis()
    blob = await r.get(state_key)
    if not blob:
        raise HTTPException(400, "State expired")
    await r.delete(state_key)
    state = json.loads(blob)
    claims = await okta_oidc.complete_flow(code, state)

    # Upsert user, pin to their existing org membership (or raise if none)
    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(400, "No email in id_token")
    user = await session.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            email=email,
            display_name=claims.get("name"),
            external_idp="okta",
            external_subject=claims["sub"],
            mfa_enrolled=True,  # assume IdP enforces MFA
        )
        session.add(user)
        await session.flush()

    mem = await session.scalar(select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1))
    if not mem:
        raise HTTPException(403, "User has no org — ask an admin to invite you")

    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(mem.organization_id),
        seat_role=mem.seat_role,
        scopes=_seat_scopes(mem.seat_role),
        amr=["sso", "okta", "oidc"],
    )
    raw, h = mint_refresh_token()
    session.add(
        RefreshSession(
            user_id=user.id, token_hash=h,
            expires_at=refresh_token_expiry(),
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    )
    user.last_login_at = datetime.now(tz=timezone.utc)
    await session.commit()

    await record_auth(
        session, org_id=str(mem.organization_id), actor=f"user:{user.id}",
        event="sso.login", outcome="allow",
        payload={"provider": "okta-oidc"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Set refresh as httpOnly cookie; return access in the body
    resp = RedirectResponse(
        url=f"/app/sso-callback#access_token={access}",
        status_code=302,
    )
    resp.set_cookie(
        "kynara_refresh", raw,
        httponly=True, secure=True, samesite="lax",
        max_age=get_settings().jwt_refresh_ttl_seconds,
    )
    return resp


# ------------------------------------------------------------------- SAML ----
class SamlStartIn(BaseModel):
    connection_id: str
    return_to: str | None = None


@router.post("/saml/start")
async def saml_start(body: SamlStartIn, session: AsyncSession = Depends(_session)):
    conn = await session.get(SsoConnection, uuid.UUID(body.connection_id))
    if not conn or conn.protocol != "saml" or not conn.is_enabled:
        raise HTTPException(404, "SAML connection not found")
    url = saml.build_login_redirect(conn, body.return_to)
    return {"redirect_url": url}


@router.post("/saml/acs")
async def saml_acs(
    request: Request,
    connection_id: str,
    session: AsyncSession = Depends(_session),
):
    conn = await session.get(SsoConnection, uuid.UUID(connection_id))
    if not conn or conn.protocol != "saml":
        raise HTTPException(404, "SAML connection not found")

    form = await request.form()
    post_data = dict(form)
    try:
        parsed = saml.parse_acs(conn, post_data, request.url.netloc)
    except PermissionError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))

    email = (parsed["attributes"].get(conn.attribute_map.get("email", "email"))
             or parsed["name_id"] or "").lower()
    if conn.email_domain_allowlist and not any(
        email.endswith("@" + d) for d in conn.email_domain_allowlist
    ):
        raise HTTPException(403, "Email domain not allowed for this connection")

    user = await session.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            email=email,
            display_name=parsed["attributes"].get(conn.attribute_map.get("name", "displayName")),
            external_idp="saml",
            external_subject=parsed["name_id"],
            mfa_enrolled=True,
        )
        session.add(user)
        await session.flush()

    mem = await session.scalar(select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1))
    if not mem:
        raise HTTPException(403, "User has no org — ask an admin to invite you")

    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(mem.organization_id),
        seat_role=mem.seat_role,
        scopes=_seat_scopes(mem.seat_role),
        amr=["sso", "saml"],
    )
    raw, h = mint_refresh_token()
    session.add(RefreshSession(user_id=user.id, token_hash=h, expires_at=refresh_token_expiry()))
    user.last_login_at = datetime.now(tz=timezone.utc)
    await session.commit()

    await record_auth(
        session, org_id=str(mem.organization_id), actor=f"user:{user.id}",
        event="sso.login", outcome="allow",
        payload={"provider": "saml", "connection": str(conn.id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    resp = RedirectResponse(url=f"/app/sso-callback#access_token={access}", status_code=302)
    resp.set_cookie("kynara_refresh", raw, httponly=True, secure=True, samesite="lax")
    return resp


@router.get("/saml/metadata")
async def saml_metadata() -> Response:
    """Return the SP metadata XML for upload into the IdP."""
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    dummy = SsoConnection(
        organization_id=uuid.UUID(int=0),
        slug="metadata", protocol="saml",
        display_name="metadata",
        idp_entity_id="about:metadata", idp_sso_url="about:metadata", idp_x509_cert="",
        attribute_map={}, email_domain_allowlist=[], is_enabled=True, enforce_for_org=False,
    )
    s = OneLogin_Saml2_Settings(saml.__dict__["_settings_dict"](dummy), sp_validation_only=True)
    return Response(content=s.get_sp_metadata(), media_type="application/xml")


def _seat_scopes(seat_role: str) -> list[str]:
    return {
        "owner":     ["*"],
        "admin":     ["*"],
        "developer": ["agents.*", "tools.*", "policies.read", "audit.read"],
        "auditor":   ["audit.*", "policies.read"],
        "member":    ["self.read"],
    }.get(seat_role, ["self.read"])


# ── Generic OIDC (any IdP via stored SsoConnection) ───────────────────────

class OidcStartIn(BaseModel):
    connection_id: str | None = None  # use a specific connection
    email: str | None = None          # OR route by email domain


@router.post("/oidc/start")
async def oidc_start(
    body: OidcStartIn,
    session: AsyncSession = Depends(_session),
):
    """Initiate OIDC login for any registered connection. Accepts connection_id or email."""
    conn: SsoConnection | None = None

    if body.connection_id:
        conn = await session.get(SsoConnection, uuid.UUID(body.connection_id))
    elif body.email:
        email_lower = body.email.lower().strip()

        # Primary lookup: find the user in Kynara → their org → that org's SSO connection.
        # This ensures the user always lands in the org they actually belong to,
        # regardless of email domain patterns.
        user = await session.scalar(select(User).where(User.email == email_lower))
        if user:
            mem = await session.scalar(
                select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1)
            )
            if mem:
                conn = await session.scalar(
                    select(SsoConnection).where(
                        SsoConnection.organization_id == mem.organization_id,
                        SsoConnection.protocol == "oidc",
                        SsoConnection.is_enabled.is_(True),
                    )
                )

        # Fallback: domain-based lookup for users not yet in Kynara
        # (e.g. first-time SSO login before an explicit invite is sent)
        if not conn:
            domain = email_lower.split("@")[-1]
            rows = (await session.scalars(
                select(SsoConnection).where(
                    SsoConnection.protocol == "oidc",
                    SsoConnection.is_enabled.is_(True),
                )
            )).all()
            conn = next(
                (r for r in rows if domain in (r.email_domain_allowlist or [])),
                None,
            )

    if not conn or conn.protocol != "oidc" or not conn.is_enabled:
        raise HTTPException(404, "No active OIDC connection found for this domain or connection ID")
    if not conn.issuer or not conn.client_id:
        raise HTTPException(422, "Connection is missing issuer or client_id")

    settings = get_settings()
    redirect_uri = settings.public_api_url.rstrip("/") + "/api/v1/auth/sso/oidc/callback"

    cfg = OidcConfig(
        issuer=conn.issuer,
        client_id=conn.client_id,
        client_secret=conn.client_secret_enc or "",
        redirect_uri=redirect_uri,
    )

    # Generate the Redis key first and use it as the OIDC `state` parameter.
    # Auth0 (and all OIDC IdPs) echo `state` back verbatim in the callback URL,
    # so the callback can use ?state=<key> to look up the bundle — no separate
    # state_key query param needed.
    r = await _redis()
    key = f"ssos:{secrets.token_urlsafe(16)}"

    url, state_bundle = await okta_oidc.start_flow_with_config(cfg, state_override=key)
    state_bundle["connection_id"] = str(conn.id)
    state_bundle["org_id"] = str(conn.organization_id)

    await r.setex(key, 600, json.dumps(state_bundle))
    return {"redirect_url": url, "state_key": key}


@router.get("/oidc/callback")
async def oidc_callback(
    code: str,
    state: str,  # OIDC standard — IdP echoes back whatever we sent as `state`
    request: Request,
    session: AsyncSession = Depends(_session),
):
    """Handle callback for any OIDC connection (Auth0, Azure AD, Google, etc.)."""
    r = await _redis()
    blob = await r.get(state)
    if not blob:
        raise HTTPException(400, "State expired or invalid")
    await r.delete(state)
    state = json.loads(blob)

    try:
        claims = await okta_oidc.complete_flow_with_config(code, state)
    except Exception as exc:
        raise HTTPException(400, f"OIDC token exchange failed: {exc}") from exc

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(400, "No email claim in id_token")

    # Resolve which org this connection belongs to
    conn = await session.get(SsoConnection, uuid.UUID(state["connection_id"]))
    if not conn:
        raise HTTPException(404, "Connection removed")

    # Look up the user in Kynara — they must already exist and have been
    # explicitly invited to this org. SSO authenticates identity only;
    # org membership is managed separately via Kynara invites.
    user = await session.scalar(select(User).where(User.email == email))
    if not user:
        logger.warning(
            "sso.login: no Kynara user found for email=%s (conn=%s org=%s)",
            email, conn.id, conn.organization_id,
        )
        raise HTTPException(
            403,
            f"No Kynara account found for {email!r}. "
            "Ask your organisation administrator to send you an invite."
        )

    mem = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.user_id == user.id,
            OrgMembership.organization_id == conn.organization_id,
        )
    )
    if not mem:
        logger.warning(
            "sso.login: user %s (%s) has no membership in org %s (conn=%s)",
            user.id, email, conn.organization_id, conn.id,
        )
        raise HTTPException(
            403,
            f"{email!r} is not a member of this organisation. "
            "Go to Settings → Members → Invite in Kynara to add them."
        )

    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(mem.organization_id),
        seat_role=mem.seat_role,
        scopes=_seat_scopes(mem.seat_role),
        amr=["sso", "oidc"],
    )
    raw, h = mint_refresh_token()
    session.add(RefreshSession(
        user_id=user.id, token_hash=h,
        expires_at=refresh_token_expiry(),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    ))
    user.last_login_at = datetime.now(tz=timezone.utc)
    await session.commit()

    await record_auth(
        session,
        org_id=str(mem.organization_id),
        actor=f"user:{user.id}",
        event="sso.login",
        outcome="allow",
        payload={"provider": conn.display_name, "connection_id": str(conn.id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    resp = RedirectResponse(
        url=f"/app/sso-callback#access_token={access}",
        status_code=302,
    )
    resp.set_cookie(
        "kynara_refresh", raw,
        httponly=True, secure=True, samesite="lax",
        max_age=get_settings().jwt_refresh_ttl_seconds,
    )
    return resp


# ── Domain lookup (for login page UX) ─────────────────────────────────────

@router.get("/lookup")
async def lookup_by_email(email: str, session: AsyncSession = Depends(_session)):
    """Return the SSO connection(s) for the given email.

    Lookup order:
    1. Find the user in Kynara → their org → that org's SSO connection (most precise).
    2. Fall back to email domain matching for users not yet in Kynara.

    The login page calls this so it can show the SSO button and pass the right connection_id.
    """
    if "@" not in email:
        return {"connections": []}

    email_lower = email.lower().strip()

    # Primary: user-based lookup
    user = await session.scalar(select(User).where(User.email == email_lower))
    if user:
        mem = await session.scalar(
            select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1)
        )
        if mem:
            rows = (await session.scalars(
                select(SsoConnection).where(
                    SsoConnection.organization_id == mem.organization_id,
                    SsoConnection.is_enabled.is_(True),
                )
            )).all()
            if rows:
                return {"connections": [
                    {"id": str(r.id), "display_name": r.display_name, "protocol": r.protocol}
                    for r in rows
                ]}

    # Fallback: domain-based lookup
    domain = email_lower.split("@")[-1]
    all_conns = (await session.scalars(
        select(SsoConnection).where(SsoConnection.is_enabled.is_(True))
    )).all()
    matches = [
        {"id": str(r.id), "display_name": r.display_name, "protocol": r.protocol}
        for r in all_conns
        if domain in (r.email_domain_allowlist or [])
    ]
    return {"connections": matches}
