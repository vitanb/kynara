"""Super admin endpoints — platform-wide org and user management."""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, require_superadmin
from app.core.logging import get_logger

logger = get_logger("kynara.admin")
from app.db.session import SessionLocal
from app.models import (
    Agent, ApprovalRequest, OrgInvite, OrgMembership, Organization,
    RefreshSession, Subscription, User,
)


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
    email_error: str | None = None


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
    email_error: str | None = None
    if body.email:
        from app.core.config import get_settings
        from app.core.email import send_email, invite_email_content
        try:
            s = get_settings()
            invite_url = f"{s.app_url}/invite?token={raw_token}"
            logger.info(
                "admin.invite_email.attempt",
                to=body.email,
                invite_url=invite_url,
                from_address=s.email_from_address,
                resend_key_set=bool(s.resend_api_key),
                smtp_host_set=bool(s.smtp_host),
                mailchannels_enabled=s.mailchannels_enabled,
            )
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
            logger.info("admin.invite_email.sent", to=body.email)
        except Exception as exc:
            email_error = str(exc)
            logger.error(
                "admin.invite_email.failed",
                to=body.email,
                error=email_error,
                exc_info=True,
            )

    return AdminInviteOut(
        invite_id=str(invite.id),
        token=raw_token,
        expires_at=expires_at.isoformat(),
        seat_role=body.seat_role,
        email=body.email,
        email_error=email_error,
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


# ─── superadmin: view a customer org's agents & approvals (support) ───────────
# Read-only, cross-tenant visibility for support. Every access is recorded in the
# TARGET org's tamper-evident audit log so customers can see when Kynara staff
# looked at their data. No cross-org mutation is exposed here.

class AdminAgentOut(BaseModel):
    id: str
    slug: str
    display_name: str
    description: str | None
    mode: str
    model: str | None
    is_active: bool
    daily_action_budget: int
    last_action_at: str | None
    created_at: str | None


class AdminApprovalOut(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    on_behalf_of_user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    status: str
    matched_policy_id: str | None
    reviewed_by_user_id: str | None
    reviewed_at: str | None
    expires_at: str
    created_at: str


async def _superadmin_support_audit(
    session: AsyncSession, principal: Principal, org_id: str, event: str, count: int
) -> None:
    """Best-effort: record cross-tenant support access in the target org's audit log.
    Never fails the read — support visibility must not depend on the audit write."""
    try:
        await record_admin(
            session,
            org_id=org_id,
            actor=f"superadmin:{principal.user_id}",
            event_type=event,
            resource_type="organization",
            resource_id=org_id,
            payload={"superadmin_user_id": principal.user_id, "count": count},
            outcome="allow",
        )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning("superadmin.support_audit_failed event=%s org=%s", event, org_id, exc_info=True)


@router.get("/orgs/{org_id}/agents", response_model=list[AdminAgentOut])
async def list_org_agents(
    org_id: str,
    principal: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    """Read-only: view a customer org's agents for support. Access is audited."""
    org = await session.get(Organization, uuid.UUID(org_id))
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")
    rows = (await session.scalars(
        select(Agent).where(Agent.organization_id == org.id).order_by(Agent.created_at.desc())
    )).all()
    # Serialize BEFORE the audit commit — a commit expires ORM attributes.
    out = [AdminAgentOut(
        id=str(r.id), slug=r.slug, display_name=r.display_name,
        description=r.description, mode=r.mode, model=r.model,
        is_active=r.is_active, daily_action_budget=r.daily_action_budget,
        last_action_at=r.last_action_at.isoformat() if r.last_action_at else None,
        created_at=r.created_at.isoformat() if r.created_at else None,
    ) for r in rows]
    await _superadmin_support_audit(session, principal, org_id, "superadmin.viewed_agents", len(out))
    return out


@router.get("/orgs/{org_id}/approvals", response_model=list[AdminApprovalOut])
async def list_org_approvals(
    org_id: str,
    status_filter: str | None = None,
    limit: int = 100,
    principal: Principal = Depends(require_superadmin),
    session: AsyncSession = Depends(_session),
):
    """Read-only: view a customer org's approval requests for support. Access is audited."""
    org = await session.get(Organization, uuid.UUID(org_id))
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")
    q = select(ApprovalRequest).where(ApprovalRequest.organization_id == org.id)
    if status_filter and status_filter != "all":
        q = q.where(ApprovalRequest.status == status_filter)
    rows = (await session.scalars(
        q.order_by(ApprovalRequest.created_at.desc()).limit(max(1, min(limit, 500)))
    )).all()
    out = [AdminApprovalOut(
        id=str(r.id), subject_type=r.subject_type, subject_id=r.subject_id,
        on_behalf_of_user_id=r.on_behalf_of_user_id, action=r.action,
        resource_type=r.resource_type, resource_id=r.resource_id, status=r.status,
        matched_policy_id=r.matched_policy_id,
        reviewed_by_user_id=str(r.reviewed_by_user_id) if r.reviewed_by_user_id else None,
        reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
        expires_at=r.expires_at.isoformat(), created_at=r.created_at.isoformat(),
    ) for r in rows]
    await _superadmin_support_audit(session, principal, org_id, "superadmin.viewed_approvals", len(out))
    return out
