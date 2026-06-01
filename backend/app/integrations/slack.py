"""Slack integration — post approval requests as Block Kit messages with Approve/Reject buttons.

Setup (one-time):
  1. Create a Slack app at https://api.slack.com/apps
  2. Add Bot Token Scopes: chat:write, chat:write.public
  3. Enable Interactivity and set Request URL to:
       https://<your-domain>/api/v1/integrations/slack/callback
  4. Set env vars: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APPROVAL_CHANNEL

Flow:
  require_approval decision → post_approval_message() → Slack channel
  Reviewer clicks Approve/Reject → Slack POSTs to /callback → handle_callback()
  → update ApprovalRequest.status → send updated Slack message
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger("kynara.integrations.slack")

SLACK_API = "https://slack.com/api"


def _headers() -> dict[str, str]:
    token = get_settings().slack_bot_token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def _action_id(approval_id: str, action: str) -> str:
    """Encode approval_id into the Slack action_id so it survives the callback."""
    return f"kynara_{action}_{approval_id}"


def _parse_action_id(action_id: str) -> tuple[str, str] | None:
    """Return (action, approval_id) from a kynara action_id, or None."""
    parts = action_id.split("_", 2)
    if len(parts) == 3 and parts[0] == "kynara":
        return parts[1], parts[2]
    return None


def build_approval_blocks(
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    context: dict,
) -> list[dict]:
    """Build Block Kit blocks for an approval request message."""
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M UTC") if expires_at.tzinfo else expires_at.strftime("%Y-%m-%d %H:%M")
    resource_str = f"{resource_type}/{resource_id}" if resource_type and resource_id else resource_type or resource_id or "—"

    # Surface key attrs (amount, env, etc.) if present
    attr_lines = []
    for key in ("amount_cents", "environment", "requester_role", "service_name"):
        if key in resource_attrs:
            val = resource_attrs[key]
            if key == "amount_cents":
                attr_lines.append(f"*Amount:* ${val/100:,.2f}")
            else:
                attr_lines.append(f"*{key.replace('_',' ').title()}:* {val}")

    details = "\n".join([
        f"*Agent:* `{subject_id}`",
        f"*Action:* `{action}`",
        f"*Resource:* `{resource_str}`",
        *(attr_lines),
        f"*Policy:* {policy_name or '—'}",
        f"*Expires:* {expires_str}",
        f"*Approval ID:* `{approval_id}`",
    ])

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔔 Approval Required — Kynara", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": details},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✓ Approve", "emoji": True},
                    "style": "primary",
                    "action_id": _action_id(approval_id, "approve"),
                    "value": "approve",
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Approve this action?"},
                        "text": {"type": "mrkdwn", "text": f"You are approving `{action}` for agent `{subject_id}`."},
                        "confirm": {"type": "plain_text", "text": "Yes, approve"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✗ Reject", "emoji": True},
                    "style": "danger",
                    "action_id": _action_id(approval_id, "reject"),
                    "value": "reject",
                },
            ],
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Sent by Kynara · <https://kynaraai.com|kynaraai.com>"}],
        },
    ]


def build_resolved_blocks(
    approval_id: str,
    action: str,
    outcome: str,
    reviewer: str,
    note: str | None,
) -> list[dict]:
    """Replace the approval buttons with a resolved state."""
    icon = "✅" if outcome == "approved" else "❌"
    label = "Approved" if outcome == "approved" else "Rejected"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{icon} *{label}* by {reviewer}\n*Action:* `{action}`  *ID:* `{approval_id}`"
                        + (f"\n*Note:* {note}" if note else ""),
            },
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Resolved via Kynara"}],
        },
    ]


async def post_approval_message(
    *,
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    context: dict,
    channel: str | None = None,
    _org_integration=None,
) -> str | None:
    """Post an approval request to Slack. Returns the message ts (used to update later), or None on failure.

    _org_integration: OrgIntegration model row — used for per-org tokens.
    Falls back to global env vars for self-hosted deployments.
    """
    from app.core.encryption import decrypt
    s = get_settings()

    # Resolve token: per-org config takes precedence over global env vars
    if _org_integration and _org_integration.slack_enabled:
        bot_token = decrypt(_org_integration.slack_bot_token_enc or "") or s.slack_bot_token
        target_channel = channel or _org_integration.slack_channel_id or s.slack_approval_channel
        webhook_url = decrypt(_org_integration.slack_webhook_url_enc or "") or None
    else:
        bot_token = s.slack_bot_token
        target_channel = channel or s.slack_approval_channel
        webhook_url = None

    if not bot_token and not webhook_url:
        log.debug("Slack not configured for this org — skipping approval notification")
        return None
    if not target_channel and not webhook_url:
        log.warning("Slack channel not set — cannot post approval")
        return None

    blocks = build_approval_blocks(
        approval_id=approval_id, subject_id=subject_id, action=action,
        resource_type=resource_type, resource_id=resource_id,
        resource_attrs=resource_attrs, policy_name=policy_name,
        expires_at=expires_at, context=context,
    )

    payload = {
        "channel": target_channel,
        "text": f"Approval required: {action} by {subject_id}",  # fallback for notifications
        "blocks": blocks,
    }

    # Use resolved token (per-org or global)
    headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json; charset=utf-8"} if bot_token else _headers()

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=payload)
        data = r.json()
        if not data.get("ok"):
            log.error("Slack post failed: %s", data.get("error"))
            return None
        ts = data["ts"]
        log.info("Slack approval message posted: ts=%s channel=%s approval=%s", ts, target_channel, approval_id)
        return ts
    except Exception as exc:
        log.exception("Slack post_approval_message error: %s", exc)
        return None


async def update_approval_message(
    *,
    channel: str,
    ts: str,
    approval_id: str,
    action: str,
    outcome: str,
    reviewer: str,
    note: str | None = None,
) -> None:
    """Update the Slack message after an approval is resolved."""
    s = get_settings()
    if not s.slack_bot_token:
        return
    blocks = build_resolved_blocks(approval_id=approval_id, action=action, outcome=outcome, reviewer=reviewer, note=note)
    payload = {"channel": channel, "ts": ts, "blocks": blocks, "text": f"Approval {outcome}: {action}"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(f"{SLACK_API}/chat.update", headers=_headers(), json=payload)
    except Exception as exc:
        log.exception("Slack update_approval_message error: %s", exc)


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack's X-Slack-Signature header to prevent spoofed callbacks."""
    s = get_settings()
    if not s.slack_signing_secret:
        log.warning("SLACK_SIGNING_SECRET not set — accepting all callbacks (insecure)")
        return True
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:  # reject stale requests (> 5 min)
            return False
        base = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac.new(
            s.slack_signing_secret.encode(), base.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def parse_interaction_payload(form_body: bytes) -> dict[str, Any]:
    """Parse Slack's URL-encoded interaction payload."""
    from urllib.parse import parse_qs, unquote_plus
    parsed = parse_qs(form_body.decode())
    raw = parsed.get("payload", ["{}"])[0]
    return json.loads(raw)
