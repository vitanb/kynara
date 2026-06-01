"""Approval notification dispatcher.

Looks up the org's OrgIntegration row and fires Slack and/or Teams
notifications concurrently. Failures are logged but never propagate
to the caller so the decision API remains fast and reliable.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApprovalRequest

log = logging.getLogger("kynara.integrations.notify")


async def _get_org_integration(session: AsyncSession, org_id: str):
    """Fetch the OrgIntegration row for this org, or None."""
    try:
        import uuid
        from app.models.org_integration import OrgIntegration
        return await session.scalar(
            select(OrgIntegration).where(
                OrgIntegration.organization_id == uuid.UUID(org_id)
            )
        )
    except Exception:
        return None


async def notify_approval_created(approval: ApprovalRequest, session: AsyncSession | None = None) -> None:
    """Send Slack and/or Teams notification for a new approval.

    Uses the org's per-org integration config (OrgIntegration) if available,
    falls back to global env vars for self-hosted deployments.
    Runs both notifications concurrently. Errors are caught internally.
    """
    from app.integrations.slack import post_approval_message
    from app.integrations.teams import post_approval_card

    approval_id = str(approval.id)
    org_id = str(approval.organization_id)

    # Look up per-org integration config
    org_integration = None
    if session:
        org_integration = await _get_org_integration(session, org_id)
    else:
        # Create a short-lived session just for the lookup
        try:
            from app.db.session import SessionLocal
            async with SessionLocal() as s:
                org_integration = await _get_org_integration(s, org_id)
        except Exception as exc:
            log.warning("Could not fetch OrgIntegration for org %s: %s", org_id, exc)

    kwargs = dict(
        approval_id=approval_id,
        subject_id=approval.subject_id,
        action=approval.action,
        resource_type=approval.resource_type,
        resource_id=approval.resource_id,
        resource_attrs=approval.resource_attrs or {},
        policy_name=approval.matched_policy_id,
        expires_at=approval.expires_at,
        context=approval.context or {},
    )

    async def _slack():
        try:
            ts = await post_approval_message(**kwargs, _org_integration=org_integration)
            if ts:
                log.info("Slack notified: approval=%s ts=%s", approval_id, ts)
        except Exception as exc:
            log.exception("Slack notification failed for approval %s: %s", approval_id, exc)

    async def _teams():
        try:
            teams_kwargs = {k: v for k, v in kwargs.items() if k != "context"}
            ok = await post_approval_card(**teams_kwargs, _org_integration=org_integration)
            if ok:
                log.info("Teams notified: approval=%s", approval_id)
        except Exception as exc:
            log.exception("Teams notification failed for approval %s: %s", approval_id, exc)

    await asyncio.gather(_slack(), _teams(), return_exceptions=True)
