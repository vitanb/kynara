"""Org invite endpoints — create invite links, accept them."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.auth.passwords import hash_password
from app.auth.tokens import mint_access_token, mint_refresh_token, refresh_token_expiry
from app.billing.quota import enforce_seat_limit
from app.db.session import SessionLocal
from app.models import OrgMembership, Organization, OrgInvite, RefreshSession, Subscription, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invites", tags=["invites"])

INVITE_TTL_DAYS = 7

# Roles that a regular org admin/owner can invite (not admin)
REGULAR_INVITE_ROLES = {"developer", "auditor", "member"}
# All valid invite roles
ALL_INVITE_ROLES = {"admin", "developer", "auditor", "member"}


async def _session():
    async with SessionLocal() as s:
        yield s


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ----------------------------------------------------------- create invite --
class InviteIn(BaseModel):
    email: EmailStr | None = None
    seat_role: str = "developer"


class InviteOut(BaseModel):
    invite_id: str
    token: str          # returned once — store or share this
    expires_at: str
    seat_role: str
    email: str | None


@router.post("", response_model=InviteOut, status_code=201)
async def create_invite(
    body: InviteIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    # Only owner, admin, or superadmin can create invites
    if principal.seat_role not in ("owner", "admin") and not principal.is_superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can invite members")

    if body.seat_role not in ALL_INVITE_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid seat role")

    # Only superadmins can invite someone as admin
    if body.seat_role == "admin" and not principal.is_superadmin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only super admins can invite users with the admin role"
        )

    # Regular owner/admin can only invite developer, auditor, or member
    if not principal.is_superadmin and body.seat_role not in REGULAR_INVITE_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only invite developers, auditors, or members"
        )

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    # Resolve org name and inviter display name for the email
    org = await session.get(Organization, principal.org_id)
    inviter = await session.get(User, principal.user_id)

    # If the invited email already has a Kynara account, immediately create
    # the OrgMembership — no need for them to click an invite link.
    existing_user = await session.scalar(
        select(User).where(User.email == body.email.lower().strip())
    ) if body.email else None

    if existing_user:
        existing_mem = await session.scalar(
            select(OrgMembership).where(
                OrgMembership.organization_id == principal.org_id,
                OrgMembership.user_id == existing_user.id,
            )
        )
        if not existing_mem:
            session.add(OrgMembership(
                organization_id=principal.org_id,
                user_id=existing_user.id,
                seat_role=body.seat_role,
            ))
            await session.commit()
        # Return a synthetic invite response — no pending token needed
        return InviteOut(
            invite_id="direct",
            token="",
            expires_at=expires_at.isoformat(),
            seat_role=body.seat_role,
            email=body.email,
        )

    invite = OrgInvite(
        organization_id=principal.org_id,
        created_by_user_id=principal.user_id,
        email=body.email,
        seat_role=body.seat_role,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(invite)
    await session.commit()

    # Send invite email automatically when an address is provided
    if body.email and org:
        from app.core.config import get_settings
        from app.core.email import send_email, invite_email_content
        try:
            s = get_settings()
            invite_url = f"{s.app_url}/invite?token={raw_token}"
            html, plain = invite_email_content(
                invite_url=invite_url,
                org_name=org.name,
                seat_role=body.seat_role,
                inviter_name=inviter.display_name if inviter else None,
            )
            await send_email(
                to=body.email,
                subject=f"You're invited to join {org.name} on Kynara",
                html_body=html,
                text_body=plain,
            )
        except Exception:
            # Non-fatal — the invite link is still returned so the admin can share it manually
            logger.exception("Failed to send invite email to %s", body.email)

    return InviteOut(
        invite_id=str(invite.id),
        token=raw_token,
        expires_at=expires_at.isoformat(),
        seat_role=body.seat_role,
        email=body.email,
    )


# ---------------------------------------------------------- list invites --
class InviteSummary(BaseModel):
    invite_id: str
    email: str | None
    seat_role: str
    expires_at: str
    created_at: str
    invited_by_email: str | None
    invited_by_name: str | None
    used: bool
    revoked: bool


@router.get("", response_model=list[InviteSummary])
async def list_invites(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    if principal.seat_role not in ("owner", "admin") and not principal.is_superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can list invites")

    rows = (await session.scalars(
        select(OrgInvite)
        .where(OrgInvite.organization_id == principal.org_id)
        .order_by(OrgInvite.created_at.desc())
    )).all()

    # Fetch all inviters in one pass
    inviter_ids = list({i.created_by_user_id for i in rows})
    inviters: dict = {}
    if inviter_ids:
        for u in (await session.scalars(select(User).where(User.id.in_(inviter_ids)))).all():
            inviters[u.id] = u

    return [
        InviteSummary(
            invite_id=str(i.id),
            email=i.email,
            seat_role=i.seat_role,
            expires_at=i.expires_at.isoformat(),
            created_at=i.created_at.isoformat(),
            invited_by_email=inviters[i.created_by_user_id].email if i.created_by_user_id in inviters else None,
            invited_by_name=inviters[i.created_by_user_id].display_name if i.created_by_user_id in inviters else None,
            used=i.used_at is not None,
            revoked=i.revoked,
        )
        for i in rows
    ]


# ---------------------------------------------------------- get invite info --
class InviteInfo(BaseModel):
    invite_id: str
    org_name: str
    seat_role: str
    email: str | None
    valid: bool


@router.get("/{token}", response_model=InviteInfo)
async def get_invite(token: str, session: AsyncSession = Depends(_session)):
    invite = await session.scalar(
        select(OrgInvite).where(OrgInvite.token_hash == _hash_token(token))
    )
    if not invite:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")

    org = await session.get(Organization, invite.organization_id)
    valid = (
        not invite.revoked
        and invite.used_at is None
        and invite.expires_at > datetime.now(tz=timezone.utc)
    )
    return InviteInfo(
        invite_id=str(invite.id),
        org_name=org.name if org else "Unknown",
        seat_role=invite.seat_role,
        email=invite.email,
        valid=valid,
    )


# --------------------------------------------------------- accept invite --
class AcceptIn(BaseModel):
    token: str
    email: EmailStr
    password: str
    display_name: str


class AcceptOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


@router.post("/accept", response_model=AcceptOut)
async def accept_invite(body: AcceptIn, session: AsyncSession = Depends(_session)):
    invite = await session.scalar(
        select(OrgInvite).where(OrgInvite.token_hash == _hash_token(body.token))
    )
    if not invite or invite.revoked or invite.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite is invalid or already used")
    if invite.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite has expired")
    if invite.email and invite.email.lower() != body.email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invite is for a different email address")

    # Get or create user
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if not user:
        if len(body.password) < 8:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be at least 8 characters")
        user = User(
            email=body.email.lower(),
            display_name=body.display_name,
            password_hash=hash_password(body.password),
        )
        session.add(user)
        await session.flush()

    # Check not already a member
    existing_mem = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.organization_id == invite.organization_id,
            OrgMembership.user_id == user.id,
        )
    )
    if existing_mem:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member of this organization")

    # Enforce seat limit before adding the new member
    await enforce_seat_limit(session, str(invite.organization_id))

    # Create membership
    membership = OrgMembership(
        organization_id=invite.organization_id,
        user_id=user.id,
        seat_role=invite.seat_role,
    )
    session.add(membership)

    # Mark invite as used
    invite.used_at = datetime.now(tz=timezone.utc)
    invite.used_by_user_id = user.id

    await session.flush()

    # Mint tokens
    from app.api.v1.auth import _default_scopes_for_seat
    from app.core.config import get_settings
    access = mint_access_token(
        user_id=str(user.id),
        org_id=str(invite.organization_id),
        seat_role=invite.seat_role,
        scopes=_default_scopes_for_seat(invite.seat_role),
        amr=["pwd"],
    )
    raw_refresh, refresh_hash = mint_refresh_token()
    session.add(RefreshSession(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_token_expiry(),
    ))
    await session.commit()

    return AcceptOut(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=get_settings().jwt_access_ttl_seconds,
    )


# --------------------------------------------------------- revoke invit