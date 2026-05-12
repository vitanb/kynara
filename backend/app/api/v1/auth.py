"""Authentication endpoints — password login, refresh, logout, me, register."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_auth
from app.auth.dependencies import Principal, get_principal
from app.auth.passwords import needs_rehash, hash_password, verify_password
from app.auth.tokens import (
    hash_refresh_token,
    mint_access_token,
    mint_refresh_token,
    refresh_token_expiry,
)
from app.core.telemetry import auth_events_total
from app.db.session import SessionLocal
from app.models import OrgMembership, Organization, PasswordResetToken, RefreshSession, Subscription, User

RESET_TTL_SECONDS = 3600  # 1 hour

router = APIRouter(prefix="/auth", tags=["auth"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ------------------------------------------------------------------- schemas --
class LoginIn(BaseModel):
    email: EmailStr
    password: str
    org_id: str | None = None  # which org to activate this session against


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class MeOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    org_id: str
    seat_role: str
    scopes: list[str]
    mfa_enrolled: bool
    timezone: str | None = None
    avatar_url: str | None = None
    is_superadmin: bool = False


class UpdateMeIn(BaseModel):
    display_name: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None


# --------------------------------------------------------------------- login --
@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(_session)):
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not user.password_hash:
        auth_events_total.labels(event="login_failure").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not verify_password(body.password, user.password_hash):
        auth_events_total.labels(event="login_failure").inc()
        mem = await session.scalar(
            select(OrgMembership).where(OrgMembership.user_id == user.id).limit(1)
        )
        if mem:
            await record_auth(
                session,
                org_id=str(mem.organization_id),
                actor=f"user:{user.id}",
                event="login.failure",
                outcome="deny",
                payload={"email": user.email, "reason": "bad_password"},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    membership = await _pick_org(session, user, body.org_id)

    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(membership.organization_id),
        seat_role=membership.seat_role,
        scopes=_default_scopes_for_seat(membership.seat_role),
        amr=["pwd"] + (["mfa"] if user.mfa_enrolled else []),
        is_superadmin=user.is_superadmin,
    )
    raw_refresh, refresh_hash = mint_refresh_token()
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_token_expiry(),
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    )

    user.last_login_at = datetime.now(tz=timezone.utc)
    await session.commit()

    await record_auth(
        session,
        org_id=str(membership.organization_id),
        actor=f"user:{user.id}",
        event="login.success",
        outcome="allow",
        payload={"email": user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    auth_events_total.labels(event="login_success").inc()

    from app.core.config import get_settings
    return TokenOut(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=get_settings().jwt_access_ttl_seconds,
    )


# --------------------------------------------------------------------- refresh
class RefreshIn(BaseModel):
    refresh_token: str
    org_id: str | None = None


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, request: Request, session: AsyncSession = Depends(_session)):
    token_hash = hash_refresh_token(body.refresh_token)
    row = await session.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash))
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    if row.revoked:
        await _revoke_chain(session, row)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected")
    if row.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")

    row.revoked = True
    user = await session.get(User, row.user_id)
    assert user
    membership = await _pick_org(session, user, body.org_id)

    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(membership.organization_id),
        seat_role=membership.seat_role,
        scopes=_default_scopes_for_seat(membership.seat_role),
        amr=["refresh"],
        is_superadmin=user.is_superadmin,
    )
    raw_refresh, refresh_hash = mint_refresh_token()
    new_row = RefreshSession(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_token_expiry(),
        parent_id=row.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    session.add(new_row)
    await session.commit()

    auth_events_total.labels(event="refresh").inc()
    from app.core.config import get_settings
    return TokenOut(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=get_settings().jwt_access_ttl_seconds,
    )


@router.post("/logout", status_code=204)
async def logout(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(_session)):
    if principal.user_id:
        from sqlalchemy import update
        await session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == principal.user_id, RefreshSession.revoked.is_(False))
            .values(revoked=True)
        )
        await session.commit()
    auth_events_total.labels(event="logout").inc()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
async def me(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(_session)):
    if not principal.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "API key principals have no /me")
    user = await session.get(User, principal.user_id)
    assert user
    return MeOut(
        user_id=principal.user_id,
        email=user.email,
        display_name=user.display_name,
        org_id=principal.org_id,
        seat_role=principal.seat_role,
        scopes=list(principal.scopes),
        mfa_enrolled=user.mfa_enrolled,
        timezone=user.timezone,
        avatar_url=user.avatar_url,
        # Use is_superadmin from the JWT claim, not the DB.
        # SSO tokens intentionally omit superadmin so a user who happens to
        # be a superadmin doesn't get elevated privileges via an SSO session.
        is_superadmin=principal.is_superadmin,
    )


@router.patch("/me", response_model=MeOut)
async def update_me(
    body: UpdateMeIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    if not principal.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "API key principals have no /me")
    user = await session.get(User, principal.user_id)
    assert user
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or None
    if body.timezone is not None:
        user.timezone = body.timezone or None
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url or None
    await session.commit()
    await session.refresh(user)
    return MeOut(
        user_id=principal.user_id,
        email=user.email,
        display_name=user.display_name,
        org_id=principal.org_id,
        seat_role=principal.seat_role,
        scopes=list(principal.scopes),
        mfa_enrolled=user.mfa_enrolled,
        timezone=user.timezone,
        avatar_url=user.avatar_url,
        is_superadmin=user.is_superadmin,
    )


# ------------------------------------------------------------------ helpers ---
async def _pick_org(session, user, explicit_org_id: str | None) -> OrgMembership:
    if explicit_org_id:
        m = await session.scalar(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.organization_id == explicit_org_id,
            )
        )
        if not m:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No membership in that org")
        return m
    # Default to the most-recently-joined org (created_at DESC).
    m = await session.scalar(
        select(OrgMembership)
        .where(OrgMembership.user_id == user.id)
        .order_by(OrgMembership.created_at.desc())
        .limit(1)
    )
    if not m:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no org memberships")
    return m


async def _revoke_chain(session, row: RefreshSession) -> None:
    from sqlalchemy import update
    await session.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == row.user_id, RefreshSession.revoked.is_(False))
        .values(revoked=True)
    )


def _default_scopes_for_seat(seat_role: str) -> list[str]:
    return {
        "owner":     ["*"],
        "admin":     ["*"],
        "developer": ["agents.*", "tools.*", "policies.read", "audit.read", "billing.read"],
        "auditor":   ["audit.*", "policies.read", "agents.read", "tools.read"],
        "member":    ["self.read", "self.update", "agents.read"],
    }.get(seat_role, ["self.read"])


# ------------------------------------------------------------------- register --
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    org_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("org_name")
    @classmethod
    def org_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("org_name must not be blank")
        return v.strip()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] + "-" + secrets.token_hex(4)


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, session: AsyncSession = Depends(_session)):
    existing = await session.scalar(select(User).where(User.email == body.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # Prevent duplicate org names — case-insensitive match
    existing_org = await session.scalar(
        select(Organization).where(Organization.name == body.org_name)
    )
    if existing_org:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An organization with that name already exists. Please choose a different name."
        )

    user = User(
        email=body.email.lower(),
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.flush()

    org = Organization(name=body.org_name, slug=_slugify(body.org_name), plan="free")
    session.add(org)
    await session.flush()

    membership = OrgMembership(organization_id=org.id, user_id=user.id, seat_role="owner")
    session.add(membership)

    _now = datetime.now(tz=timezone.utc)
    session.add(Subscription(
        organization_id=org.id, plan="free", status="trialing",
        seats_included=3, decisions_included=10_000, overage_cents_per_1k=0,
        current_period_start=_now,
        current_period_end=_now + timedelta(days=14),
    ))

    await session.commit()

    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(org.id),
        seat_role="owner",
        scopes=_default_scopes_for_seat("owner"),
        amr=["pwd"],
        is_superadmin=user.is_superadmin,
    )
    raw_refresh, refresh_hash = mint_refresh_token()
    session.add(RefreshSession(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_token_expiry(),
    ))
    await session.commit()

    from app.core.config import get_settings
    return TokenOut(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=get_settings().jwt_access_ttl_seconds,
    )


# ----------------------------------------------------------------- me/orgs --
class OrgOut(BaseModel):
    org_id: str
    org_name: str
    slug: str
    seat_role: str
    plan: str


@router.get("/me/orgs", response_model=list[OrgOut])
async def me_orgs(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(_session)):
    """List all orgs the current user belongs to (for org switching)."""
    from sqlalchemy.orm import selectinload
    rows = await session.scalars(
        select(OrgMembership)
        .options(selectinload(OrgMembership.organization))
        .where(OrgMembership.user_id == principal.user_id)
    )
    return [
        OrgOut(
            org_id=str(m.organization_id),
            org_name=m.organization.name,
            slug=m.organization.slug,
            seat_role=m.seat_role,
            plan=m.organization.plan,
        )
        for m in rows
    ]


# -------------------------------------------------------- forgot password --
class ForgotPasswordIn(BaseModel):
    email: EmailStr


@router.post("/forgot-password", status_code=202)
async def forgot_password(body: ForgotPasswordIn, session: AsyncSession = Depends(_session)):
    """Always returns 202 — we never reveal whether the email exists."""
    from app.core.config import get_settings
    from app.core.email import send_email, reset_email_content

    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if not user:
        return {"detail": "If that email is registered you will receive a reset link shortly."}

    existing = await session.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    for tok in existing:
        tok.used_at = datetime.now(tz=timezone.utc)

    raw = secrets.token_urlsafe(48)
    tok_hash = hashlib.sha256(raw.encode()).hexdigest()
    reset_tok = PasswordResetToken(
        user_id=user.id,
        token_hash=tok_hash,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=RESET_TTL_SECONDS),
    )
    session.add(reset_tok)
    await session.commit()

    s = get_settings()
    reset_url = f"{s.app_url}/reset-password?token={raw}"
    html, plain = reset_email_content(reset_url, user.display_name)

    import logging as _log
    try:
        await send_email(
            to=user.email,
            subject="Reset your Kynara password",
            html_body=html,
            text_body=plain,
        )
    except Exception:
        _log.getLogger(__name__).exception(
            "Password-reset email failed for %s — reset link: %s", user.email, reset_url
        )

    return {"detail": "If that email is registered you will receive a reset link shortly."}


# --------------------------------------------------------- reset password --
class ResetPasswordIn(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.post("/reset-password", status_code=200)
async def reset_password(body: ResetPasswordIn, session: AsyncSession = Depends(_session)):
    tok_hash = hashlib.sha256(body.token.encode()).hexdigest()
    token = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == tok_hash)
    )
    if not token or token.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or already-used reset link")
    if token.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset link has expired")

    user = await session.get(User, token.user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.password_hash = hash_password(body.new_password)
    token.used_at = datetime.now(tz=timezone.utc)

    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked.is_(False))
        .values(revoked=True)
    )

    await session.commit()
    auth_events_total.labels(event="password_reset").inc()
    return {"detail": "Password updated. Please log in with your new password."}
