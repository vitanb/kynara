"""Async email sending.

Transport priority (first match wins):
  1. MailChannels HTTP API  — MAILCHANNELS_ENABLED=true  (Cloudflare, free, no API key)
  2. Resend HTTP API        — RESEND_API_KEY set          (legacy, free tier 100/day)
  3. SMTP                  — SMTP_HOST set                (Gmail app-password, SendGrid…)
  4. Console log           — nothing configured           (dev fallback)

MailChannels DNS records required in Cloudflare (all TXT):
  Name: @               Value: v=spf1 include:relay.mailchannels.net ~all
  Name: _mailchannels   Value: v=mc1 cfid=<your-cloudflare-account-id>
  Name: mailchannels._domainkey  (DKIM, optional but recommended — see config.py)
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ================================================================= dispatcher ==

async def send_email(*, to: str, subject: str, html_body: str, text_body: str) -> None:
    """Send an email using the best available transport."""
    s = get_settings()

    if s.mailchannels_enabled:
        await _send_mailchannels(to=to, subject=subject, html_body=html_body, text_body=text_body)
    elif s.resend_api_key:
        await _send_resend(to=to, subject=subject, html_body=html_body, text_body=text_body)
    elif s.smtp_host:
        await asyncio.to_thread(_send_smtp, to, subject, html_body, text_body)
    else:
        logger.warning(
            "[EMAIL — no transport configured, logging link instead]\n"
            "To: %s\nSubject: %s\n\n%s",
            to, subject, text_body,
        )


# ================================================================= transports ==

async def _send_mailchannels(*, to: str, subject: str, html_body: str, text_body: str) -> None:
    """Send via MailChannels (Cloudflare's email partner). No API key required —
    authentication is domain-based (SPF + optional DKIM)."""
    import httpx  # lazy import
    s = get_settings()

    # Parse "Display Name <addr@domain.com>" into separate fields
    from_name, from_email = _parse_from(s.email_from_address)

    personalization: dict = {"to": [{"email": to}]}

    # DKIM signing (optional but strongly recommended for deliverability)
    if s.mailchannels_dkim_domain and s.mailchannels_dkim_private_key:
        personalization["dkim_domain"] = s.mailchannels_dkim_domain
        personalization["dkim_selector"] = s.mailchannels_dkim_selector
        personalization["dkim_private_key"] = s.mailchannels_dkim_private_key

    payload = {
        "from": {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_body},
            {"type": "text/html",  "value": html_body},
        ],
        "personalizations": [personalization],
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post("https://api.mailchannels.net/tx/v1/send", json=payload)

    if resp.status_code not in (200, 201, 202):
        logger.error("MailChannels error %s: %s", resp.status_code, resp.text[:300])
        raise RuntimeError(f"MailChannels {resp.status_code}: {resp.text[:200]}")

    logger.info("Email sent via MailChannels to %s — %s", to, subject)


async def _send_resend(*, to: str, subject: str, html_body: str, text_body: str) -> None:
    import httpx  # lazy import
    s = get_settings()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
            json={
                "from": s.email_from_address,
                "to": [to],
                "subject": subject,
                "html": html_body,
                "text": text_body,
            },
        )

    if resp.status_code not in (200, 201):
        logger.error("Resend error %s: %s", resp.status_code, resp.text[:300])
        raise RuntimeError(f"Resend {resp.status_code}: {resp.text[:200]}")

    logger.info("Email sent via Resend to %s — %s", to, subject)


def _send_smtp(to: str, subject: str, html_body: str, text_body: str) -> None:
    s = get_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = s.email_from_address
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as server:
        if s.smtp_tls:
            server.ehlo()
            server.starttls()
            server.ehlo()
        if s.smtp_username:
            server.login(s.smtp_username, s.smtp_password)
        server.send_message(msg)
    logger.info("Email sent via SMTP to %s — %s", to, subject)


# ================================================================== helpers ==

def _parse_from(from_address: str) -> tuple[str, str]:
    """Split 'Display Name <addr@domain.com>' into (name, email).
    Falls back to (email, email) if no display name is present."""
    if "<" in from_address and from_address.endswith(">"):
        name, rest = from_address.rsplit("<", 1)
        return name.strip(), rest.rstrip(">").strip()
    return from_address.strip(), from_address.strip()


# ================================================================== templates ==

def _base_html(content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#05080F;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#0D1421;border-radius:12px;border:1px solid rgba(148,163,184,0.1)">
        <tr>
          <td style="padding:28px 36px 20px;border-bottom:1px solid rgba(148,163,184,0.08)">
            <span style="color:#fff;font-size:17px;font-weight:700;letter-spacing:-0.3px">⬡ Kynara</span>
          </td>
        </tr>
        <tr><td style="padding:32px 36px">{content}</td></tr>
        <tr>
          <td style="padding:16px 36px 24px;border-top:1px solid rgba(148,163,184,0.08)">
            <p style="margin:0;color:#475569;font-size:12px;line-height:1.5">
              Sent by Kynara · AI agent permission control plane.<br>
              If you didn't expect this, you can safely ignore it.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def reset_email_content(reset_url: str, display_name: str | None) -> tuple[str, str]:
    name = display_name or "there"
    body = f"""
      <h2 style="margin:0 0 8px;color:#fff;font-size:20px;font-weight:700">Reset your password</h2>
      <p style="margin:0 0 6px;color:#94A3B8;font-size:14px">Hi {name},</p>
      <p style="margin:0 0 24px;color:#CBD5E1;font-size:14px;line-height:1.6">
        Click the button below to reset your Kynara password.
        This link expires in <strong style="color:#fff">1 hour</strong>.
      </p>
      <table cellpadding="0" cellspacing="0" style="margin-bottom:24px">
        <tr><td style="background:#4F46E5;border-radius:8px">
          <a href="{reset_url}" style="display:inline-block;padding:13px 28px;color:#fff;
             font-size:14px;font-weight:600;text-decoration:none">Reset password →</a>
        </td></tr>
      </table>
      <p style="margin:0;color:#475569;font-size:12px;word-break:break-all">
        Or copy: <a href="{reset_url}" style="color:#818CF8">{reset_url}</a>
      </p>"""
    plain = (
        f"Hi {name},\n\nReset your Kynara password (expires in 1 hour):\n\n{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    return _base_html(body), plain


def invite_email_content(
    invite_url: str, org_name: str, seat_role: str, inviter_name: str | None,
) -> tuple[str, str]:
    role_label = {
        "owner": "Owner", "admin": "Admin", "developer": "Developer",
        "auditor": "Auditor", "member": "Member",
    }.get(seat_role, seat_role.title())
    from_line = (
        f"<strong style='color:#fff'>{inviter_name}</strong> invited you"
        if inviter_name else "You've been invited"
    )
    body = f"""
      <h2 style="margin:0 0 8px;color:#fff;font-size:20px;font-weight:700">
        You're invited to join {org_name}
      </h2>
      <p style="margin:0 0 20px;color:#CBD5E1;font-size:14px;line-height:1.6">
        {from_line} to join <strong style="color:#fff">{org_name}</strong> on Kynara
        as a <span style="color:#818CF8;font-weight:600">{role_label}</span>.
      </p>
      <table cellpadding="0" cellspacing="0" style="margin-bottom:24px">
        <tr><td style="background:#4F46E5;border-radius:8px">
          <a href="{invite_url}" style="display:inline-block;padding:13px 28px;color:#fff;
             font-size:14px;font-weight:600;text-decoration:none">Accept invitation →</a>
        </td></tr>
      </table>
      <p style="margin:0;color:#475569;font-size:12px;word-break:break-all">
        Link expires in 7 days · <a href="{invite_url}" style="color:#818CF8">{invite_url}</a>
      </p>"""
    plain = (
        f"You've been invited to join {org_name} on Kynara as {role_label}.\n\n"
        f"Accept invite (expires 7 days):\n\n{invite_url}\n\n"
        "If you didn't expect this, you can safely ignore it."
    )
    return _base_html(body), plain
