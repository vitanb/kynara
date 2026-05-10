"""Org details, membership, and danger-zone endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal, require_seat
from app.db.session import SessionLocal
from app.models import ApiKey, Organization, OrgMembership, RefreshSession, User

router = APIRouter(prefix="/org", tags=["org"])


async def _session():
    async with SessionLocal() as s:
        yield s


@router.get("")
async def get_org(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Return details of the current org."""
    org = await session.get(Organization, uuid.UUID(principal.org_id))
    if not org:
        raise HTTPException(404, "Organization not found")
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "region": "us-east-1",
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


@router.get("/members")
async def list_members(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Return all members of the current org. Visible to all authenticated members."""
    memberships = (await session.scalars(
        select(OrgMembership)
        .where(OrgMembership.organization_id == uuid.UUID(principal.org_id))
    )).all()

    results = []
    for m in memberships:
        user = await session.get(User, m.user_id)
        if user:
            results.append({
                "user_id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "seat_role": m.seat_role,
                "mfa_enrolled": user.mfa_enrolled,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            })
    return results


VALID_ROLES = {"owner", "admin", "developer", "auditor", "member"}


@router.patch("/members/{user_id}")
async def update_member_role(
    user_id: str,
    seat_role: str = Body(..., embed=True),
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Change the seat role of an org member. Owner/admin only.
    Admins cannot promote to owner."""
    if seat_role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

    org_id = uuid.UUID(principal.org_id)
    target_id = uuid.UUID(user_id)

    # Admins cannot grant owner
    if principal.seat_role == "admin" and seat_role == "owner":
        raise HTTPException(403, "Admins cannot promote members to owner")

    # Cannot change your own role
    if str(target_id) == principal.user_id:
        raise HTTPException(400, "You cannot change your own role")

    membership = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.organization_id == org_id,
            OrgMembership.user_id == target_id,
        )
    )
    if not membership:
        raise HTTPException(404, "Member not found in this organization")

    # Protect against demoting the last owner
    if membership.seat_role == "owner":
        owner_count = await session.scalar(
            select(OrgMembership).where(
                OrgMembership.organization_id == org_id,
                OrgMembership.seat_role == "owner",
            ).with_only_columns(OrgMembership.user_id)
        )
        owners = (await session.scalars(
            select(OrgMembership).where(
                OrgMembership.organization_id == org_id,
                OrgMembership.seat_role == "owner",
            )
        )).all()
        if len(owners) <= 1 and seat_role != "owner":
            raise HTTPException(400, "Cannot demote the only owner. Promote another member first.")

    membership.seat_role = seat_role
    await session.commit()
    return {"user_id": user_id, "seat_role": seat_role}


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Remove a member from the org. Owner/admin only. Cannot remove yourself or the last owner."""
    org_id = uuid.UUID(principal.org_id)
    target_id = uuid.UUID(user_id)

    if str(target_id) == principal.user_id:
        raise HTTPException(400, "You cannot remove yourself from the organization")

    membership = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.organization_id == org_id,
            OrgMembership.user_id == target_id,
        )
    )
    if not membership:
        raise HTTPException(404, "Member not found in this organization")

    if membership.seat_role == "owner":
        owners = (await session.scalars(
            select(OrgMembership).where(
                OrgMembership.organization_id == org_id,
                OrgMembership.seat_role == "owner",
            )
        )).all()
        if len(owners) <= 1:
            raise HTTPException(400, "Cannot remove the only owner.")

    # Revoke all active sessions for this user in this org
    await session.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == target_id, RefreshSession.revoked.is_(False))
        .values(revoked=True)
    )

    await session.delete(membership)
    await session.commit()
    return {"removed": user_id}


# ── Danger zone ────────────────────────────────────────────────────────────


@router.post("/rotate-api-keys")
async def rotate_api_keys(
    principal: Principal = Depends(require_seat("owner")),
    session: AsyncSession = Depends(_session),
):
    """Revoke every active API key for this org. Owner only."""
    org_id = uuid.UUID(principal.org_id)
    result = await session.execute(
        update(ApiKey)
        .where(ApiKey.organization_id == org_id, ApiKey.revoked.is_(False))
        .values(revoked=True)
        .returning(ApiKey.id)
    )
    revoked_ids = result.scalars().all()
    await session.commit()
    return {"revoked_count": len(revoked_ids)}


@router.post("/revoke-sessions")
async def revoke_all_sessions(
    principal: Principal = Depends(require_seat("owner")),
    session: AsyncSession = Depends(_session),
):
    """Revoke every active refresh session for all members of this org. Owner only."""
    org_id = uuid.UUID(principal.org_id)

    # Collect all user_ids in this org
    memberships = (await session.scalars(
        select(OrgMembership).where(OrgMembership.organization_id == org_id)
    )).all()
    user_ids = [m.user_id for m in memberships]

    if not user_ids:
        return {"revoked_count": 0}

    result = await session.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id.in_(user_ids),
            RefreshSession.revoked.is_(False),
        )
        .values(revoked=True)
        .returning(RefreshSession.id)
    )
    revoked_ids = result.scalars().all()
    await session.commit()
    return {"revoked_count": len(revoked_ids)}


@router.delete("")
async def delete_org(
    principal: Principal = Depends(require_seat("owner")),
    session: AsyncSession = Depends(_session),
):
    """Permanently delete the organization and all associated data. Owner only."""
    org_id = uuid.UUID(principal.org_id)
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    # Cascade delete is defined at the DB level (ondelete="CASCADE") for child tables
    # that reference organizations.id. RefreshSession only references users, so we
    # need to revoke those manually before deleting the org.
    memberships = (await session.scalars(
        select(OrgMembership).where(OrgMembership.organization_id == org_id)
    )).all()
    user_ids = [m.user_id for m in memberships]
    if user_ids:
        await session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id.in_(user_ids))
            .values(revoked=True)
        )

    await session.delete(org)
    await session.commit()
    return {"deleted": True}
