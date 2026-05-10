"""Public contact-form endpoint — no auth required."""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.core.email import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact", tags=["contact"])

OWNER_EMAIL = "vitanreddy@gmail.com"


class ContactForm(BaseModel):
    name: str
    email: EmailStr
    message: str


@router.post("")
async def submit_contact(form: ContactForm):
    """Accept a contact form submission and email it to the site owner."""
    subject = f"[Kynara Contact] Message from {form.name}"

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#05080F;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#0D1421;border-radius:12px;border:1px solid rgba(148,163,184,0.1)">
        <tr>
          <td style="padding:28px 36px 20px;border-bottom:1px solid rgba(148,163,184,0.08)">
            <span style="color:#fff;font-size:17px;font-weight:700;letter-spacing:-0.3px">⬡ Kynara — Contact form</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 36px">
            <p style="margin:0 0 4px;color:#64748B;font-size:12px;text-transform:uppercase;letter-spacing:0.06em">From</p>
            <p style="margin:0 0 20px;color:#F1F5F9;font-size:15px;font-weight:600">{form.name} &lt;{form.email}&gt;</p>

            <p style="margin:0 0 4px;color:#64748B;font-size:12px;text-transform:uppercase;letter-spacing:0.06em">Message</p>
            <div style="background:#080C14;border:1px solid rgba(148,163,184,0.08);border-radius:8px;padding:16px 20px;margin-bottom:24px">
              <p style="margin:0;color:#CBD5E1;font-size:14px;line-height:1.7;white-space:pre-wrap">{form.message}</p>
            </div>

            <a href="mailto:{form.email}" style="display:inline-block;background:#4F46E5;color:#fff;
               text-decoration:none;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px">
              Reply to {form.name} →
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 36px 24px;border-top:1px solid rgba(148,163,184,0.08)">
            <p style="margin:0;color:#475569;font-size:12px">Sent via kynara.ai contact form.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text_body = (
        f"New contact form submission\n\n"
        f"From: {form.name} <{form.email}>\n\n"
        f"Message:\n{form.message}\n\n"
        f"Reply to: {form.email}"
    )

    try:
        await send_email(
            to=OWNER_EMAIL,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
    except Exception as exc:
        logger.error("Contact form email failed: %s", exc)
        # Still return 200 so the form doesn't expose internal errors publicly;
        # the message is logged and can be retrieved from server logs.

    return {"ok": True}
