"""Chat integration callback endpoints.

POST /api/v1/integrations/slack/callback
    Receives Slack interactive component payloads (button clicks).
    Verifies X-Slack-Signature and updates the ApprovalRequest.

POST /api/v1/integrations/teams/callback
    Receives Teams action callbacks (Power Automate / bot framework).
    Verifies HMAC signature and updates the ApprovalRequest.

GET  /api/v1/approvals/{approval_id}/approve-link
GET  /api/v1/approvals/{approval_id}/reject-link
    One-click deep links embedded in Teams cards and email notifications.
    Requires the reviewer to be authenticated (cookie session or query token).
    Redirects to the Kynara UI approval page after resolving.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.slack import (
    _parse_action_id,
    parse_interaction_payload,
    update_approval_message,
    verify_slack_signature,
)
from app.integrations.teams import verify_teams_signature
from app.models import ApprovalRequest

log = logging.getLogger("kynara.integrations")

router = APIRouter(prefix="/integrations", tags=["integrations"])


async def _session():
    async with SessionLocal() as s:
        yield s


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _resolve_approval(
    session: AsyncSession,
    approval_id: str,
    outcome: str,
    reviewer_name: str,
    note: str | None,
    org_id: str | None = None,
) -> ApprovalRequest:
    """Set approval status; raise 404/400/409 as appropriate."""
    try:
        uid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(400, "Invalid approval ID")

    row = await session.get(ApprovalRequest, uid)
    if not row:
        raise HTTPException(404, "Approval request not found")
    if org_id and str(row.organization_id) != org_id:
        raise HTTPException(404, "Approval request not found")
    if row.status != "pending":
        raise HTTPException(409, f"Approval is already {row.status}")
    if row.expires_at < datetime.now(tz=timezone.utc):
        row.status = "expired"
        await session.commit()
        raise HTTPException(410, "Approval has expired")

    row.status = outcome
    row.reviewed_at = datetime.now(tz=timezone.utc)
    row.review_note = note

    await record_admin(
        session,
        org_id=str(row.organization_id),
        actor=f"integration:{reviewer_name}",
        event_type=f"approval.{outcome}",
        resource_type="approval",
        resource_id=approval_id,
        payload={"outcome": outcome, "note": note, "via": "chat_integration"},
    )
    await session.commit()
    return row


# ──────────────────────────────────────────────────────────────────────────────
#  Slack callback
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/slack/callback", include_in_schema=False)
async def slack_callback(
    request: Request,
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_signature: str = Header(default=""),
    session: AsyncSession = Depends(_session),
):
    body = await request.body()

    # Verify signature
    if not verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(401, "Invalid Slack signature")

    payload = parse_interaction_payload(body)
    payload_type = payload.get("type")

    if payload_type != "block_actions":
        return Response(status_code=200)  # ignore non-action events

    actions = payload.get("actions", [])
    if not actions:
        return Response(status_code=200)

    action = actions[0]
    action_id: str = action.get("action_id", "")
    parsed = _parse_action_id(action_id)
    if not parsed:
        return Response(status_code=200)

    outcome, approval_id = parsed   # e.g. ("approve", "uuid...")
    if outcome not in ("approve", "reject"):
        return Response(status_code=200)

    # Resolve to "approved" / "rejected"
    final_outcome = "approved" if outcome == "approve" else "rejected"

    user = payload.get("user", {})
    reviewer_name = user.get("name") or user.get("id") or "slack_user"

    # Get channel + message ts for later update
    channel_id = payload.get("channel", {}).get("id", "")
    message_ts = payload.get("message", {}).get("ts", "")

    try:
        row = await _resolve_approval(
            session, approval_id, final_outcome, reviewer_name, note=None
        )
    except HTTPException as e:
        # Return a visible error to Slack via response_action
        return Response(
            content=json.dumps({
                "response_action": "update",
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f"⚠️ {e.detail}"}}],
            }),
            media_type="application/json",
        )

    # Update the original message to show resolved state
    if channel_id and message_ts:
        await update_approval_message(
            channel=channel_id, ts=message_ts,
            approval_id=approval_id, action=row.action,
            outcome=final_outcome, reviewer=reviewer_name,
        )

    # Respond to Slack with updated blocks (replaces buttons)
    icon = "✅" if final_outcome == "approved" else "❌"
    label = "Approved" if final_outcome == "approved" else "Rejected"
    return Response(
        content=json.dumps({
            "response_action": "update",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{icon} *{label}* by @{reviewer_name}\n*Action:* `{row.action}`  *ID:* `{approval_id}`",
                    },
                }
            ],
        }),
        media_type="application/json",
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Teams callback
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/teams/callback", include_in_schema=False)
async def teams_callback(
    request: Request,
    x_kynara_signature: str = Header(default=""),
    session: AsyncSession = Depends(_session),
):
    body = await request.body()

    if not verify_teams_signature(body, x_kynara_signature):
        raise HTTPException(401, "Invalid Teams callback signature")

    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    approval_id = data.get("approval_id")
    outcome_raw = data.get("outcome")  # "approve" or "reject"
    reviewer = data.get("reviewer") or "teams_user"
    note = data.get("note")

    if not approval_id or outcome_raw not in ("approve", "reject"):
        raise HTTPException(400, "Missing approval_id or outcome")

    final_outcome = "approved" if outcome_raw == "approve" else "rejected"

    row = await _resolve_approval(session, approval_id, final_outcome, reviewer, note)
    return {"status": "ok", "outcome": final_outcome, "approval_id": approval_id, "action": row.action}


# ──────────────────────────────────────────────────────────────────────────────
#  Deep-link endpoints for Teams cards and email buttons
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/approvals/{approval_id}/approve-link")
async def approve_link(
    approval_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """One-click approve — requires authenticated session. Used in Teams/email buttons."""
    reviewer = principal.user_id or principal.api_key_id or "unknown"
    await _resolve_approval(session, approval_id, "approved", reviewer, note="Approved via link", org_id=principal.org_id)
    s = get_settings()
    return RedirectResponse(url=f"{s.app_url}/approvals/{approval_id}?resolved=approved")


@router.get("/approvals/{approval_id}/reject-link")
async def reject_link(
    approval_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """One-click reject — requires authenticated session."""
    reviewer = principal.user_id or principal.api_key_id or "unknown"
    await _resolve_approval(session, approval_id, "rejected", reviewer, note="Rejected via link", org_id=principal.org_id)
    s = get_settings()
    return RedirectResponse(url=f"{s.app_url}/approvals/{approval_id}?resolved=rejected")
