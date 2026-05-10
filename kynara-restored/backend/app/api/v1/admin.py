"""Super admin endpoints — platform-wide org and user management."""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, require_superadmin
from app.db.session import SessionLocal
from app.models import OrgInvite, OrgMembership, Organization, RefreshSession, Subscription, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["superadmin"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ─── response schemas ────────────────────────────────────────────────────────

class AdminMemberOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    seat_role: str
    is_active: bool
    is_superadmin: bool
    mfa_enrolled: bool
    last_login_at: str | None


class AdminSubscriptionOut(BaseModel):
    plan: str
    status: str
    seats_included: int
    decisions_included: int
    current_period_end: str | None


class AdminOrgOut(BaseModel):
    org_id: str
    name: str
    slug: str
    plan: str
    created_at: str | None
    member_count: int
    members: list[AdminMemberOut]
    subscription: AdminSubscriptionOut | None


class AdminUserOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    is_active: bool
    is_superadmin: bool
    mfa_enrolled: bool
    last_login_at: str | None
    orgs: list[dict]  # [{org_id, org_name, seat_role}]
    created_at: str | None


# ─── list all orgs ───────────────────────────────────────────────────────────

@router.get("/orgs", response_model=list[AdminOrgOut])
async def list_all_orgs(
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    orgs = (await session.scalars(
        select(Organization).order_by(Organization.created_at.desc())
    )).all()

    result = []
    for org in orgs:
        memberships = (await session.scalars(
            select(OrgMembership).where(OrgMembership.organization_id == org.id)
        )).all()

        members = []
        for m in memberships:
            user = await session.get(User, m.user_id)
            if user:
                members.append(AdminMemberOut(
                    user_id=str(user.id),
                    email=user.email,
                    display_name=user.display_name,
                    seat_role=m.seat_role,
                    is_active=user.is_active,
                    is_superadmin=user.is_superadmin,
                    mfa_enrolled=user.mfa_enrolled,
                    last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
                ))

        sub = await session.scalar(
            select(Subscription)
            .where(Subscription.organization_id == org.id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub_out = AdminSubscriptionOut(
            plan=sub.plan,
            status=sub.status,
            seats_included=sub.seats_included,
            decisions_included=sub.decisions_included,
            current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        ) if sub else None

        result.append(AdminOrgOut(
            org_id=str(org.id),
            name=org.name,
            slug=org.slug,
            plan=org.plan,
            created_at=org.created_at.isoformat() if org.created_at else None,
            member_count=len(members),
            members=members,
            subscription=sub_out,
        ))
    return result



# ─── create org (superadmin) ─────────────────────────────────────────────────

def _admin_slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] + "-" + secrets.token_hex(4)


class CreateOrgIn(BaseModel):
    name: str
    plan: str = "free"


class CreateOrgOut(BaseModel):
    org_id: str
    name: str
    slug: str
    plan: str


@router.post("/orgs", response_model=CreateOrgOut, status_code=201)
async def create_org(
    body: CreateOrgIn,
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Org name must not be blank")

    # Prevent duplicate names
    existing = await session.scalar(
        select(Organization).where(Organization.name == name)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An organization with that name already exists")

    valid_plans = {"free", "starter", "pro", "enterprise"}
    if body.plan not in valid_plans:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid plan: {body.plan}")

    org = Organization(name=name, slug=_admin_slugify(name), plan=body.plan)
    session.add(org)
    await session.flush()

    _now = datetime.now(tz=timezone.utc)
    seats = {"free": 3, "starter": 10, "pro": 50, "enterprise": 500}.get(body.plan, 3)
    decisions = {"free": 10_000, "starter": 100_000, "pro": 1_000_000, "enterprise": 10_000_000}.get(body.plan, 10_000)
    session.add(Subscription(
        organization_id=org.id,
        plan=body.plan,
        status="active",
        seats_included=seats,
        decisions_included=decisions,
        overage_cents_per_1k=0,
        current_period_start=_now,
        current_period_end=_now + timedelta(days=365),
    ))
    await session.commit()

    return CreateOrgOut(
        org_id=str(org.id),
        name=org.name,
        slug=org.slug,
        plan=org.plan,
    )


# ─── update org ──────────────────────────────────────────────────────────────

class UpdateOrgIn(BaseModel):
    name: str | None = None
    plan: str | None = None


@router.patch("/orgs/{org_id}")
async def update_org(
    org_id: str,
    body: UpdateOrgIn,
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    org = await session.get(Organization, uuid.UUID(org_id))
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")
    if body.name is not None:
        org.name = body.name.strip()
    if body.plan is not None:
        valid_plans = {"free", "starter", "pro", "enterprise"}
        if body.plan not in valid_plans:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"plan must be one of: {', '.join(sorted(valid_plans))}")
        org.plan = body.plan
        # Sync subscription plan too
        sub = await session.scalar(
            select(Subscription)
            .where(Subscription.organization_id == org.id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        if sub:
            sub.plan = body.plan
    await session.commit()
    return {"org_id": org_id, "name": org.name, "plan": org.plan}


# ─── delete org ──────────────────────────────────────────────────────────────

@router.delete("/orgs/{org_id}", status_code=204)
async def delete_org(
    org_id: str,
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    org = await session.get(Organization, uuid.UUID(org_id))
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")
    await session.delete(org)
    await session.commit()


# ─── list all users ──────────────────────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserOut])
async def list_all_users(
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    users = (await session.scalars(
        select(User).order_by(User.created_at.desc())
    )).all()

    result = []
    for user in users:
        memberships = (await session.scalars(
            select(OrgMembership).where(OrgMembership.user_id == user.id)
        )).all()
        orgs = []
        for m in memberships:
            org = await session.get(Organization, m.organization_id)
            if org:
                orgs.append({"org_id": str(org.id), "org_name": org.name, "seat_role": m.seat_role})

        result.append(AdminUserOut(
            user_id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            is_superadmin=user.is_superadmin,
            mfa_enrolled=user.mfa_enrolled,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
            orgs=orgs,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ))
    return result


# ─── update user ─────────────────────────────────────────────────────────────

class UpdateUserIn(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserIn,
    principal: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    user = await session.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or None
    if body.is_active is not None:
        user.is_active = body.is_active
        if not body.is_active:
            # Revoke all sessions on deactivation
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(RefreshSession)
                .where(RefreshSession.user_id == user.id, RefreshSession.revoked.is_(False))
                .values(revoked=True)
            )
    if body.is_superadmin is not None:
        user.is_superadmin = body.is_superadmin
    await session.commit()
    return {
        "user_id": user_id,
        "is_active": user.is_active,
        "is_superadmin": user.is_superadmin,
        "display_name": user.display_name,
    }


# ─── update org member seat role ─────────────────────────────────────────────

VALID_ROLES = {"owner", "admin", "developer", "auditor", "member"}


@router.patch("/orgs/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: str,
    user_id: str,
    seat_role: str = Body(..., embed=True),
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    if seat_role not in VALID_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"seat_role must be one of: {', '.join(sorted(VALID_ROLES))}")
    membership = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.organization_id == uuid.UUID(org_id),
            OrgMembership.user_id == uuid.UUID(user_id),
        )
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    membership.seat_role = seat_role
    await session.commit()
    return {"org_id": org_id, "user_id": user_id, "seat_role": seat_role}


# ─── remove org member ───────────────────────────────────────────────────────

@router.delete("/orgs/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: str,
    user_id: str,
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    membership = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.organization_id == uuid.UUID(org_id),
            OrgMembership.user_id == uuid.UUID(user_id),
        )
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    await session.delete(membership)
    await session.commit()


# ─── superadmin: invite member to any org ────────────────────────────────────

class AdminInviteIn(BaseModel):
    email: str | None = None
    seat_role: str = "developer"


class AdminInviteOut(BaseModel):
    invite_id: str
    token: str
    expires_at: str
    seat_role: str
    email: str | None


ALL_INVITE_ROLES = {"admin", "developer", "auditor", "member"}
INVITE_TTL_DAYS = 7


def _hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/orgs/{org_id}/invites", response_model=AdminInviteOut, status_code=201)
async def admin_create_invite(
    org_id: str,
    body: AdminInviteIn,
    principal: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    """Super admin can create an invite link for any org, any role."""
    org = await session.get(Organization, uuid.UUID(org_id))
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")

    if body.seat_role not in ALL_INVITE_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid role: {body.seat_role}")

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_invite_token(raw_token)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    invite = OrgInvite(
        organization_id=uuid.UUID(org_id),
        created_by_user_id=principal.user_id,
        email=body.email or None,
        seat_role=body.seat_role,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(invite)
    await session.commit()

    # Attempt to send invite email if address provided
    if body.email:
        from app.core.config import get_settings
        from app.core.email import send_email, invite_email_content
        try:
            s = get_settings()
            invite_url = f"{s.app_url}/invite?token={raw_token}"
            html, plain = invite_email_content(
                invite_url=invite_url,
                org_name=org.name,
                seat_role=body.seat_role,
                inviter_name="Kynara Super Admin",
            )
            await send_email(
                to=body.email,
                subject=f"You're invited to join {org.name} on Kynara",
                html_body=html,
                text_body=plain,
            )
        except Exception:
            logger.exception("Failed to send admin invite email to %s", body.email)

    return AdminInviteOut(
        invite_id=str(invite.id),
        token=raw_token,
        expires_at=expires_at.isoformat(),
        seat_role=body.seat_role,
        email=body.email,
    )


@router.get("/orgs/{org_id}/invites", response_model=list[dict])
async def admin_list_invites(
    org_id: str,
    _: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    """List all invites for a given org (superadmin view)."""
    org = await session.get(Organization, uuid.UUID(org_id))
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")

    rows = (await session.scalars(
        select(OrgInvite)
        .where(OrgInvite.organization_id == uuid.UUID(org_id))
        .order_by(OrgInvite.created_at.desc())
    )).all()

    return [
        {
            "invite_id": str(i.id),
            "email": i.email,
            "seat_role": i.seat_role,
            "expires_at": i.expires_at.isoformat(),
            "used": i.used_at is not None,
            "revoked": i.revoked,
        }
        for i in rows
    ]
