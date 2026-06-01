"""Approval analytics endpoints."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import ApprovalRequest

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
    }
