"""Email approval notifications.

Sends a plain-text + HTML email when an approval is required,
with one-click Approve / Reject links using the existing /approve-link
and /reject-link endpoints (authenticated via the reviewer's session).

Uses the same email transport as the rest of the app (MailChannels / SMTP).
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.core.config import get_settings
from app.core.email import send_email

log = logging.getLogger("kynara.integrations.email_notify")


def _approval_html(
    *,
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    approve_url: str,
    reject_url: str,
    kynara_url: str,
) -> tuple[str, str]:
    """Return (html_body, text_body) for the approval notification email."""
    resource_str = f"{resource_type}/{resource_id}" if resource_type and resource_id else resource_type or resource_id or "—"
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")

    # Notable attrs
    attr_rows_html = ""
    attr_rows_text = ""
    for key in ("amount_cents", "environment", "service_name", "requester_role"):
        if key in resource_attrs:
            val = resource_attrs[key]
            display = f"${val/100:,.2f}" if key == "amount_cents" else str(val)
            label = key.replace("_", " ").title()
            attr_rows_html += f"<tr><td style='color:#64748B;padding:4px 0;'>{label}</td><td style='padding:4px 0 4px 16px;color:#F1F5F9;'>{display}</td></tr>"
            attr_rows_text += f"  {label}: {display}\n"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#05080F;font-family:Inter,system-ui,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#05080F;padding:32px 16px;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#080C14;border:1px solid rgba(148,163,184,0.1);border-radius:16px;overflow:hidden;">

      <!-- Header -->
      <tr><td style="padding:24px 28px;border-bottom:1px solid rgba(148,163,184,0.08);">
        <span style="font-size:18px;font-weight:700;color:#F1F5F9;">🔔 Approval Required</span>
        <span style="margin-left:8px;font-size:12px;color:#64748B;">— Kynara</span>
      </td></tr>

      <!-- Details -->
      <tr><td style="padding:24px 28px;">
        <table cellpadding="0" cellspacing="0" style="width:100%;">
          <tr><td style="color:#64748B;padding:4px 0;">Agent</td><td style="padding:4px 0 4px 16px;color:#F1F5F9;font-family:monospace;">{subject_id}</td></tr>
          <tr><td style="color:#64748B;padding:4px 0;">Action</td><td style="padding:4px 0 4px 16px;color:#F1F5F9;font-family:monospace;">{action}</td></tr>
          <tr><td style="color:#64748B;padding:4px 0;">Resource</td><td style="padding:4px 0 4px 16px;color:#F1F5F9;">{resource_str}</td></tr>
          {attr_rows_html}
          <tr><td style="color:#64748B;padding:4px 0;">Policy</td><td style="padding:4px 0 4px 16px;color:#F1F5F9;">{policy_name or "—"}</td></tr>
          <tr><td style="color:#64748B;padding:4px 0;">Expires</td><td style="padding:4px 0 4px 16px;color:#F59E0B;">{expires_str}</td></tr>
        </table>
      </td></tr>

      <!-- Actions -->
      <tr><td style="padding:0 28px 28px;">
        <table cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding-right:12px;">
              <a href="{approve_url}" style="display:inline-block;background:#10B981;color:#fff;font-weight:700;font-size:14px;padding:12px 24px;border-radius:8px;text-decoration:none;">✓ Approve</a>
            </td>
            <td>
              <a href="{reject_url}" style="display:inline-block;background:#F43F5E;color:#fff;font-weight:700;font-size:14px;padding:12px 24px;border-radius:8px;text-decoration:none;">✕ Reject</a>
            </td>
          </tr>
        </table>
        <p style="margin-top:16px;font-size:12px;color:#64748B;">
          Or <a href="{kynara_url}/app/approvals/{approval_id}" style="color:#818CF8;">open in Kynara</a> to review with full context.
        </p>
      </td></tr>

      <!-- Footer -->
      <tr><td style="padding:16px 28px;border-top:1px solid rgba(148,163,184,0.08);font-size:11px;color:#475569;">
        Kynara · AI Agent Permission Control Plane · <a href="{kynara_url}" style="color:#6366F1;">kynaraai.com</a>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>"""

    text = f"""Approval Required — Kynara

An AI agent action requires your review.

  Agent:    {subject_id}
  Action:   {action}
  Resource: {resource_str}
{attr_rows_text}  Policy:   {policy_name or "—"}
  Expires:  {expires_str}

Approve: {approve_url}
Reject:  {reject_url}

Or open in Kynara: {kynara_url}/app/approvals/{approval_id}

---
Kynara · kynaraai.com
"""
    return html, text


async def notify_approval_email(
    *,
    approval_id: str,
    subject_id: str,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    resource_attrs: dict,
    policy_name: str | None,
    expires_at: datetime,
    recipients: list[str],
) -> bool:
    """Send approval notification email to one or more recipients."""
    if not recipients:
        return False

    s = get_settings()
    api_base = s.public_api_url.rstrip("/")
    app_url = s.app_url.rstrip("/")

    approve_url = f"{api_base}/api/v1/integrations/approvals/{approval_id}/approve-link"
    reject_url = f"{api_base}/api/v1/integrations/approvals/{approval_id}/reject-link"

    html, text = _approval_html(
        approval_id=approval_id, subject_id=subject_id, action=action,
        resource_type=resource_type, resource_id=resource_id,
        resource_attrs=resource_attrs, policy_name=policy_name,
        expires_at=expires_at, approve_url=approve_url,
        reject_url=reject_url, kynara_url=app_url,
    )

    sent = 0
    for recipient in recipients:
        try:
            await send_email(
                to=recipient.strip(),
                subject=f"Approval required: {action} by {subject_id}",
                html_body=html,
                text_body=text,
            )
            sent += 1
        except Exception as exc:
            log.exception("Failed to send approval email to %s: %s", recipient, exc)

    log.info("Approval email sent to %d/%d recipients for approval=%s", sent, len(recipients), approval_id)
    return sent > 0
