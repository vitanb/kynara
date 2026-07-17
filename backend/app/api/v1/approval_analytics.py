"""Approval analytics endpoints."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import ApprovalRequest, User
from app.policy.risk import score_approval

router = APIRouter(prefix="/approvals/analytics", tags=["approvals"])

async def _session():
    async with SessionLocal() as s:
        yield s

@router.get("")
async def approval_analytics(
    days: int = 30,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    org_uuid = uuid.UUID(principal.org_id)

    rows = (await session.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.organization_id == org_uuid,
            ApprovalRequest.created_at >= since,
        )
    )).all()

    total = len(rows)
    approved = sum(1 for r in rows if r.status == "approved")
    rejected = sum(1 for r in rows if r.status == "rejected")
    expired = sum(1 for r in rows if r.status == "expired")
    pending = sum(1 for r in rows if r.status == "pending")

    # Average resolution time (approved + rejected only)
    resolved = [r for r in rows if r.status in ("approved","rejected") and r.reviewed_at]
    avg_minutes = None
    if resolved:
        total_secs = sum((r.reviewed_at - r.created_at).total_seconds() for r in resolved)
        avg_minutes = round(total_secs / len(resolved) / 60, 1)

    # Top agents by approval count
    from collections import Counter
    agent_counts = Counter(r.subject_id for r in rows)
    top_agents = [{"agent": a, "count": c} for a, c in agent_counts.most_common(5)]

    # Top actions
    action_counts = Counter(r.action for r in rows)
    top_actions = [{"action": a, "count": c} for a, c in action_counts.most_common(5)]

    # Daily breakdown (last 14 days)
    daily: dict[str, dict] = {}
    for i in range(min(days, 14)):
        day = (datetime.now(tz=timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        daily[day] = {"approved": 0, "rejected": 0, "pending": 0, "expired": 0}
    for r in rows:
        day = r.created_at.strftime("%Y-%m-%d")
        if day in daily:
            daily[day][r.status] = daily[day].get(r.status, 0) + 1
    daily_list = [{"date": d, **v} for d, v in sorted(daily.items())]

    # ── Risk distribution (deterministic scoring; see app.policy.risk) ──────
    risk_mix = {"low": 0, "medium": 0, "high": 0}
    high_risk_approved_fast = 0  # high-risk requests approved in < 60s
    for r in rows:
        risk = score_approval(r.action, r.resource_attrs, r.context)
        risk_mix[risk["level"]] += 1
        if (
            risk["level"] == "high"
            and r.status == "approved"
            and r.reviewed_at
            and (r.reviewed_at - r.created_at).total_seconds() < 60
        ):
            high_risk_approved_fast += 1

    # ── Approver load & fatigue (OWASP AI Exchange #OVERSIGHT names
    #    'approval fatigue' as the failure mode of human oversight) ──────────
    by_reviewer: dict[str, list[ApprovalRequest]] = {}
    for r in resolved:
        if r.reviewed_by_user_id:
            by_reviewer.setdefault(str(r.reviewed_by_user_id), []).append(r)

    reviewer_names: dict[str, str] = {}
    if by_reviewer:
        users = (await session.scalars(
            select(User).where(User.id.in_([uuid.UUID(k) for k in by_reviewer]))
        )).all()
        reviewer_names = {str(u.id): (u.display_name or u.email) for u in users}

    reviewers = []
    for uid, items in by_reviewer.items():
        n = len(items)
        n_approved = sum(1 for r in items if r.status == "approved")
        rate = round(n_approved / n * 100, 1)
        secs = sorted((r.reviewed_at - r.created_at).total_seconds() for r in items)
        median_secs = secs[len(secs) // 2]
        per_week = n / max(1, days) * 7

        flags = []
        if n >= 20 and rate >= 95:
            flags.append("rubber_stamp_risk")   # near-universal approval at volume
        if n >= 10 and median_secs < 30:
            flags.append("speed_risk")          # median review under 30 seconds
        if per_week >= 100:
            flags.append("overloaded")          # unsustainable review volume

        reviewers.append({
            "user_id": uid,
            "name": reviewer_names.get(uid, uid[:8]),
            "reviewed": n,
            "approve_rate": rate,
            "median_seconds": round(median_secs, 1),
            "per_week": round(per_week, 1),
            "flags": flags,
        })
    reviewers.sort(key=lambda x: -x["reviewed"])

    return {
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "expired": expired,
        "pending": pending,
        "approval_rate": round(approved / max(1, approved + rejected) * 100, 1),
        "avg_resolution_minutes": avg_minutes,
        "top_agents": top_agents,
        "top_actions": top_actions,
        "daily": daily_list,
        "days": days,
        "risk_mix": risk_mix,
        "high_risk_approved_fast": high_risk_approved_fast,
        "reviewers": reviewers,
    }
