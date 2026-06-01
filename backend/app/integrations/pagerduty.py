"""PagerDuty integration — trigger incidents for critical Kynara events.

Events that trigger PagerDuty alerts:
  - require_approval decisions (new approval waiting)
  - agent.killed (kill switch activated or guardrail threshold breached)
  - audit.chain_broken (tamper detected)
  - anomaly.deny_rate_spike (unusual agent behavior)

Uses the PagerDuty Events API v2 (routing key / integration key).
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

log = logging.getLogger("kynara.integrations.pagerduty")

PD_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


async def _send_event(routing_key: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                PD_EVENTS_URL,
                json={"routing_key": routing_key, **payload},
                headers={"Content-Type": "application/json"},
            )
        if r.status_code not in (200, 201, 202):
            log.error("PagerDuty event failed: status=%s body=%s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:
        log.exception("PagerDuty send_event error: %s", exc)
        return False


async def notify_approval_pagerduty(
    *,
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    routing_key: str,
) -> bool:
    """Trigger a PagerDuty alert for a pending approval."""
    resource_str = f"{resource_type}/{resource_id}" if resource_type and resource_id else resource_type or resource_id or "—"
    summary = f"Kynara approval required: {action} by {subject_id}"
    from app.core.config import get_settings
    app_url = get_settings().app_url.rstrip("/")

    payload = {
        "event_action": "trigger",
        "dedup_key": f"kynara-approval-{approval_id}",
        "payload": {
            "summary": summary,
            "severity": "warning",
            "source": "kynara",
            "custom_details": {
                "approval_id": approval_id,
                "agent": subject_id,
                "action": action,
                "resource": resource_str,
                "policy": policy_name or "—",
                "expires_at": expires_at.isoformat(),
                "approve_url": f"{app_url}/app/approvals/{approval_id}",
            },
        },
        "links": [{"href": f"{app_url}/app/approvals/{approval_id}", "text": "Review in Kynara"}],
    }
    return await _send_event(routing_key, payload)


async def trigger_alert(
    *,
    routing_key: str,
    event_type: str,
    summary: str,
    severity: str = "critical",
    details: dict | None = None,
    dedup_key: str | None = None,
) -> bool:
    """Generic alert trigger for agent.killed, audit.chain_broken, anomaly events."""
    from app.core.config import get_settings
    app_url = get_settings().app_url.rstrip("/")

    payload = {
        "event_action": "trigger",
        "dedup_key": dedup_key or f"kynara-{event_type}-{id(summary)}",
        "payload": {
            "summary": f"Kynara: {summary}",
            "severity": severity,
            "source": "kynara",
            "custom_details": {"event_type": event_type, **(details or {})},
        },
        "links": [{"href": f"{app_url}/app/audit", "text": "View audit log"}],
    }
    return await _send_event(routing_key, payload)


async def resolve_alert(*, routing_key: str, dedup_key: str) -> bool:
    """Resolve a previously triggered PagerDuty alert."""
    payload = {"event_action": "resolve", "dedup_key": dedup_key}
    return await _send_event(routing_key, payload)
