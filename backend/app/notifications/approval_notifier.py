"""Approval notifications — Slack, Microsoft Teams, PagerDuty.

Call ``notify_approval_created`` / ``notify_approval_resolved`` from the
approvals router.  Both functions are fire-and-forget: they should be
wrapped in ``asyncio.create_task(...)`` at the call site so a notification
failure never blocks the approval HTTP response.

Channel configuration is resolved in priority order:
  1. Per-org settings  (org.metadata["notification_config"])
  2. Environment variables (SLACK_WEBHOOK_URL, TEAMS_WEBHOOK_URL,
     PAGERDUTY_ROUTING_KEY, APP_URL)
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("kynara.notifications")

# ─── config helpers ───────────────────────────────────────────────────────────

def _org_cfg(org: Any) -> dict:
    """Extract notification_config from org.metadata if present."""
    if org is None:
        return {}
    meta = getattr(org, "metadata", None) or {}
    if isinstance(meta, dict):
        return meta.get("notification_config", {}) or {}
    return {}


def _slack_url(org: Any) -> str | None:
    return _org_cfg(org).get("slack_webhook_url") or os.getenv("SLACK_WEBHOOK_URL")


def _teams_url(org: Any) -> str | None:
    return _org_cfg(org).get("teams_webhook_url") or os.getenv("TEAMS_WEBHOOK_URL")


def _pd_key(org: Any) -> str | None:
    return _org_cfg(org).get("pagerduty_routing_key") or os.getenv("PAGERDUTY_ROUTING_KEY")


def _app_url() -> str:
    return os.getenv("APP_URL", "https://app.kynaraai.com").rstrip("/")


# ─── HTTP helper ──────────────────────────────────────────────────────────────

async def _post_json(url: str, payload: dict) -> None:
    """POST JSON to a webhook URL.  Tries httpx first, falls back to aiohttp."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except ImportError:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()


# ─── Slack ────────────────────────────────────────────────────────────────────

async def _slack_approval_created(url: str, approval: Any) -> None:
    approval_url = f"{_app_url()}/approvals/{approval.id}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Approval Required", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Agent:*\n`{approval.subject_id}`"},
                {"type": "mrkdwn", "text": f"*Action:*\n`{approval.action}`"},
                {"type": "mrkdwn", "text": f"*Resource:*\n`{approval.resource_type or 'n/a'}/{approval.resource_id or 'n/a'}`"},
            ],
        },
    ]
    ctx = approval.context or {}
    justification = ctx.get("justification") or ctx.get("reason") or ""
    if justification:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Justification:*\n{justification}"},
        })
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                "style": "primary",
                "url": approval_url,
                "action_id": "approve",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                "style": "danger",
                "url": approval_url,
                "action_id": "reject",
            },
        ],
    })
    await _post_json(url, {"blocks": blocks})


async def _slack_approval_resolved(url: str, approval: Any, resolution: str) -> None:
    emoji = ":white_check_mark:" if resolution == "approved" else ":x:"
    text = (
        f"{emoji} Approval request *{resolution}* for agent `{approval.subject_id}` "
        f"action `{approval.action}`."
    )
    await _post_json(url, {"text": text})


# ─── Microsoft Teams ──────────────────────────────────────────────────────────

async def _teams_approval_created(url: str, approval: Any) -> None:
    approval_url = f"{_app_url()}/approvals/{approval.id}"
    ctx = approval.context or {}
    justification = ctx.get("justification") or ctx.get("reason") or "N/A"
    card = {
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
                            "text": "Approval Required",
                            "weight": "Bolder",
                            "size": "Large",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Agent", "value": str(approval.subject_id)},
                                {"title": "Action", "value": approval.action},
                                {"title": "Resource", "value": f"{approval.resource_type or 'n/a'}/{approval.resource_id or 'n/a'}"},
                                {"title": "Justification", "value": justification},
                            ],
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "Review in Kynara",
                            "url": approval_url,
                        },
                    ],
                },
            }
        ],
    }
    await _post_json(url, card)


async def _teams_approval_resolved(url: str, approval: Any, resolution: str) -> None:
    icon = "✅" if resolution == "approved" else "❌"
    card = {
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
                            "text": f"{icon} Approval {resolution}",
                            "weight": "Bolder",
                            "size": "Medium",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Agent", "value": str(approval.subject_id)},
                                {"title": "Action", "value": approval.action},
                                {"title": "Status", "value": resolution.capitalize()},
                            ],
                        },
                    ],
                },
            }
        ],
    }
    await _post_json(url, card)


# ─── PagerDuty ────────────────────────────────────────────────────────────────

_PD_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


def _pd_dedup_key(approval: Any) -> str:
    return f"kynara-approval-{approval.id}"


async def _pd_trigger(routing_key: str, approval: Any) -> None:
    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": _pd_dedup_key(approval),
        "payload": {
            "summary": (
                f"Approval required: agent {approval.subject_id} wants to "
                f"{approval.action} on {approval.resource_type or 'resource'}"
            ),
            "severity": "warning",
            "source": "kynara",
            "component": "approval_workflow",
            "custom_details": {
                "agent_id": str(approval.subject_id),
                "action": approval.action,
                "resource_type": approval.resource_type,
                "resource_id": approval.resource_id,
                "approval_url": f"{_app_url()}/approvals/{approval.id}",
            },
        },
        "links": [
            {"href": f"{_app_url()}/approvals/{approval.id}", "text": "Review in Kynara"}
        ],
    }
    await _post_json(_PD_EVENTS_URL, payload)


async def _pd_resolve(routing_key: str, approval: Any) -> None:
    payload = {
        "routing_key": routing_key,
        "event_action": "resolve",
        "dedup_key": _pd_dedup_key(approval),
    }
    await _post_json(_PD_EVENTS_URL, payload)


# ─── public API ───────────────────────────────────────────────────────────────

async def notify_approval_created(session: Any, approval: Any, org: Any) -> None:
    """Send notifications for a newly created approval request.

    Silently swallows all errors so callers can use asyncio.create_task safely.
    """
    slack_url = _slack_url(org)
    if slack_url:
        try:
            await _slack_approval_created(slack_url, approval)
        except Exception as exc:
            log.warning("slack notification failed: %s", exc)

    teams_url = _teams_url(org)
    if teams_url:
        try:
            await _teams_approval_created(teams_url, approval)
        except Exception as exc:
            log.warning("teams notification failed: %s", exc)

    pd_key = _pd_key(org)
    if pd_key:
        try:
            await _pd_trigger(pd_key, approval)
        except Exception as exc:
            log.warning("pagerduty notification failed: %s", exc)


async def notify_approval_resolved(
    session: Any, approval: Any, org: Any, resolution: str
) -> None:
    """Send notifications when an approval is approved or rejected.

    resolution should be "approved" or "rejected".
    """
    slack_url = _slack_url(org)
    if slack_url:
        try:
            await _slack_approval_resolved(slack_url, approval, resolution)
        except Exception as exc:
            log.warning("slack resolution notification failed: %s", exc)

    teams_url = _teams_url(org)
    if teams_url:
        try:
            await _teams_approval_resolved(teams_url, approval, resolution)
        except Exception as exc:
            log.warning("teams resolution notification failed: %s", exc)

    pd_key = _pd_key(org)
    if pd_key:
        try:
            await _pd_resolve(pd_key, approval)
        except Exception as exc:
            log.warning("pagerduty resolve notification failed: %s", exc)
