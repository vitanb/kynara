"""Microsoft Teams integration — post approval requests as Adaptive Cards.

Setup:
  Option A — Incoming Webhook (simple, no interactive buttons):
    1. In Teams channel → Connectors → Incoming Webhook → copy URL
    2. Set TEAMS_WEBHOOK_URL env var
    3. Approvers click the Kynara UI link in the card

  Option B — Power Automate + HTTP trigger (interactive buttons):
    1. Create a Power Automate flow with HTTP trigger → parse JSON → conditions →
       call Kynara PATCH /api/v1/approvals/{id}/approve or /reject
    2. Set TEAMS_WEBHOOK_URL to the Power Automate HTTP trigger URL
    3. Set TEAMS_CALLBACK_SECRET for request validation

The Adaptive Card includes an "Open in Kynara" button pointing to the approval
detail page, plus direct Approve/Reject action URLs calling back to Kynara's API.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime

import httpx

from app.core.config import get_settings

log = logging.getLogger("kynara.integrations.teams")


def build_approval_card(
    *,
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    kynara_base_url: str,
) -> dict:
    """Build a Teams Adaptive Card payload for an approval request."""
    resource_str = f"{resource_type}/{resource_id}" if resource_type and resource_id else resource_type or resource_id or "—"
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")

    facts = [
        {"title": "Agent", "value": subject_id},
        {"title": "Action", "value": f"`{action}`"},
        {"title": "Resource", "value": resource_str},
        {"title": "Policy", "value": policy_name or "—"},
        {"title": "Expires", "value": expires_str},
    ]

    # Surface notable resource attrs
    for key in ("amount_cents", "environment", "service_name"):
        if key in resource_attrs:
            val = resource_attrs[key]
            if key == "amount_cents":
                facts.append({"title": "Amount", "value": f"${val/100:,.2f}"})
            else:
                facts.append({"title": key.replace("_", " ").title(), "value": str(val)})

    approval_url = f"{kynara_base_url.rstrip('/')}/approvals/{approval_id}"
    api_base = kynara_base_url.rstrip("/")

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "size": "Large",
                            "weight": "Bolder",
                            "text": "🔔 Approval Required — Kynara",
                            "color": "Warning",
                        },
                        {
                            "type": "FactSet",
                            "facts": facts,
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Approval ID: `{approval_id}`",
                            "size": "Small",
                            "isSubtle": True,
                            "wrap": True,
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "✓ Approve in Kynara",
                            "url": f"{api_base}/api/v1/approvals/{approval_id}/approve-link",
                            "style": "positive",
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "✗ Reject in Kynara",
                            "url": f"{api_base}/api/v1/approvals/{approval_id}/reject-link",
                            "style": "destructive",
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "View details",
                            "url": approval_url,
                        },
                    ],
                },
            }
        ],
    }


def build_resolved_card(
    *,
    approval_id: str,
    action: str,
    outcome: str,
    reviewer: str,
    note: str | None = None,
) -> dict:
    """Card to send when an approval is resolved."""
    icon = "✅" if outcome == "approved" else "❌"
    label = "Approved" if outcome == "approved" else "Rejected"
    body = [
        {"type": "TextBlock", "weight": "Bolder", "text": f"{icon} {label} — {action}"},
        {"type": "TextBlock", "text": f"Resolved by: {reviewer}", "isSubtle": True},
    ]
    if note:
        body.append({"type": "TextBlock", "text": f"Note: {note}", "wrap": True})

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }


async def post_approval_card(
    *,
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    _org_integration=None,
) -> bool:
    """Post an approval card to Teams. Returns True on success.

    _org_integration: OrgIntegration model row — per-org webhook URL takes precedence.
    Falls back to global TEAMS_WEBHOOK_URL env var for self-hosted deployments.
    """
    from app.core.encryption import decrypt
    s = get_settings()

    if _org_integration and _org_integration.teams_enabled:
        webhook_url = decrypt(_org_integration.teams_webhook_url_enc or "") or s.teams_webhook_url
    else:
        webhook_url = s.teams_webhook_url

    if not webhook_url:
        log.debug("Teams not configured for this org — skipping approval notification")
        return False

    card = build_approval_card(
        approval_id=approval_id, subject_id=subject_id, action=action,
        resource_type=resource_type, resource_id=resource_id,
        resource_attrs=resource_attrs, policy_name=policy_name,
        expires_at=expires_at, kynara_base_url=s.public_api_url,
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                webhook_url,
                json=card,
                headers={"Content-Type": "application/json"},
            )
        if r.status_code not in (200, 202):
            log.error("Teams card post failed: status=%s body=%s", r.status_code, r.text[:200])
            return False
        log.info("Teams approval card posted: approval=%s", approval_id)
        return True
    except Exception as exc:
        log.exception("Teams post_approval_card error: %s", exc)
        return False


def verify_teams_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature from Teams callback (Power Automate pattern)."""
    s = get_settings()
    if not s.teams_callback_secret:
        log.warning("TEAMS_CALLBACK_SECRET not set — accepting all callbacks (insecure)")
        return True
    expected = hmac.new(s.teams_callback_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
