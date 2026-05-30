"""Approvals endpoints — human-in-the-loop review of require_approval decisions.

Agents poll GET /approvals/{id}/status.
Org owners/admins review the queue and approve or reject.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import ApprovalRequest

# Lazy import to avoid circular dependency — resolved at call time.
_auto_fulfill_jit: Any = None

def _get_jit_hook():
    global _auto_fulfill_jit
    if _auto_fulfill_jit is None:
        from app.api.v1.jit_grants import auto_fulfill_jit_elevation
        _auto_fulfill_jit = auto_fulfill_jit_elevation
    return _auto_fulfill_jit

router = APIRouter(prefix="/approvals", tags=["approvals"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ─── response schemas ─────────────────────────────────────────────────────────

class ApprovalOut(BaseModel):
    id: str
    organization_id: str
    subject_type: str
    subject_id: str
    on_behalf_of_user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    resource_attrs: dict
    context: dict
    matched_policy_id: str | None
    status: str
    reviewed_by_user_id: str | None
    reviewed_at: str | None
    review_note: str | None
    expires_at: str
    created_at: str

    @classmethod
    def from_orm(cls, r: ApprovalRequest) -> "ApprovalOut":
        return cls(
            id=str(r.id),
            organization_id=str(r.organization_id),
            subject_type=r.subject_type,
            subject_id=r.subject_id,
            on_behalf_of_user_id=r.on_behalf_of_user_id,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            resource_attrs=r.resource_attrs or {},
            context=r.context or {},
            matched_policy_id=r.matched_policy_id,
            status=r.status,
            reviewed_by_user_id=str(r.reviewed_by_user_id) if r.reviewed_by_user_id else None,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            review_note=r.review_note,
            expires_at=r.expires_at.isoformat(),
            created_at=r.created_at.isoformat(),
        )


class ApprovalStatusOut(BaseModel):
    id: str
    status: str  # pending | approved | rejected | expired
    review_note: str | None
    reviewed_at: str | None


class ReviewIn(BaseModel):
    note: str | None = None


class ApprovalListOut(BaseModel):
    items: list[ApprovalOut]
    total: int
    pending_count: int


# ─── helpers ──────────────────────────────────────────────────────────────────

def _require_admin(principal: Principal) -> None:
    if principal.seat_role not in ("owner", "admin"):
        raise HTTPException(403, "Requires owner or admin role")
    if not principal.user_id:
        raise HTTPException(403, "API keys may not review approvals — use a user session")


async def _get_or_404(session: AsyncSession, org_id: str, approval_id: str) -> ApprovalRequest:
    try:
        uid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(400, "Invalid approval ID")

    row = await session.get(ApprovalRequest, uid)
    if not row or str(row.organization_id) != org_id:
        raise HTTPException(404, "Approval request not found")
    return row


async def _expire_stale(session: AsyncSession, org_id: str) -> None:
    """Mark pending requests whose expiry has passed as 'expired'."""
    now = datetime.now(tz=timezone.utc)
    rows = (await session.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.organization_id == uuid.UUID(org_id),
            ApprovalRequest.status == "pending",
            ApprovalRequest.expires_at < now,
        )
    )).all()
    for r in rows:
        r.status = "expired"
    if rows:
        await session.flush()


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=ApprovalListOut)
async def list_approvals(
    status: str | None = Query(None, description="Filter by status: pending|approved|rejected|expired|all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """List approval requests for the org. Defaults to pending + recent history."""
    _require_admin(principal)

    # Auto-expire stale requests before listing
    await _expire_stale(session, principal.org_id)

    base_q = select(ApprovalRequest).where(
        ApprovalRequest.organization_id == uuid.UUID(principal.org_id),
    )

    # Status filter
    if status and status != "all":
        base_q = base_q.where(ApprovalRequest.status == status)

    # Total count for pagination
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await session.scalar(count_q)) or 0

    # Pending count (always shown in badge)
    pending_count = (await session.scalar(
        select(func.count()).where(
            ApprovalRequest.organization_id == uuid.UUID(principal.org_id),
            ApprovalRequest.status == "pending",
        )
    )) or 0

    rows = (await session.scalars(
        base_q.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)
    )).all()

    return ApprovalListOut(
        items=[ApprovalOut.from_orm(r) for r in rows],
        total=total,
        pending_count=pending_count,
    )


@router.get("/pending-count")
async def pending_count(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Lightweight endpoint for the nav badge — no auth admin check needed."""
    count = (await session.scalar(
        select(func.count()).where(
            ApprovalRequest.organization_id == uuid.UUID(principal.org_id),
            ApprovalRequest.status == "pending",
        )
    )) or 0
    return {"pending_count": count}


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(
    approval_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _require_admin(principal)
    row = await _get_or_404(session, principal.org_id, approval_id)
    return ApprovalOut.from_orm(row)


@router.get("/{approval_id}/status", response_model=ApprovalStatusOut)
async def poll_status(
    approval_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Lightweight poll for agents — returns just the status."""
    row = await _get_or_404(session, principal.org_id, approval_id)

    # Auto-expire if past deadline
    if row.status == "pending" and row.expires_at < datetime.now(tz=timezone.utc):
        row.status = "expired"
        await session.flush()

    return ApprovalStatusOut(
        id=str(row.id),
        status=row.status,
        review_note=row.review_note,
        reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalOut)
async def approve(
    approval_id: str,
    body: ReviewIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _require_admin(principal)
    row = await _get_or_404(session, principal.org_id, approval_id)

    if row.status != "pending":
        raise HTTPException(409, f"Request is already '{row.status}' and cannot be approved")
    if row.expires_at < datetime.now(tz=timezone.utc):
        row.status = "expired"
        await session.flush()
        raise HTTPException(410, "Approval request has expired")

    row.status = "approved"
    row.reviewed_by_user_id = uuid.UUID(principal.user_id)
    row.reviewed_at = datetime.now(tz=timezone.utc)
    row.review_note = body.note
    await session.flush()

    # Auto-fulfill self-service JIT elevation requests.
    try:
        await _get_jit_hook()(session, row, principal.user_id)
    except Exception as _hook_err:
        # Non-fatal — the approval is still recorded even if grant creation fails.
        import logging
        logging.getLogger("kynara.approvals").warning(
            "jit_auto_fulfill_failed: %s", _hook_err
        )

    await session.commit()
    await session.refresh(row)
    return ApprovalOut.from_orm(row)


@router.post("/{approval_id}/reject", response_model=ApprovalOut)
async def reject(
    approval_id: str,
    body: ReviewIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    _require_admin(principal)
    row = await _get_or_404(session, principal.org_id, approval_id)

    if row.status != "pending":
        raise HTTPException(409, f"Request is already '{row.status}' and cannot be rejected")
    if row.expires_at < datetime.now(tz=timezone.utc):
        row.status = "expired"
        await session.flush()
        raise HTTPException(410, "Approval request has expired")

    row.status = "rejected"
    row.reviewed_by_user_id = uuid.UUID(principal.user_id)
    row.reviewed_at = datetime.now(tz=timezone.utc)
    row.review_note = body.note
    await session.commit()
    await session.refresh(row)
    return ApprovalOut.from_orm(row)
