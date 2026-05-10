"""End-to-end example: a minimal agent that uses three tools, each gated by Kynara.

Run:
    export KYNARA_API_KEY=sk_live_...
    python examples/crm_agent.py
"""
from __future__ import annotations

import os

from kynara_sdk import Kynara, permission_required, PermissionDenied, ApprovalRequired
from kynara_sdk.context import set_current_kynara

kynara = Kynara(
    api_key=os.environ.get("KYNARA_API_KEY", "sk_live_DEMO"),
    agent_id="crm-assistant",
    user_id=os.environ.get("KYNARA_USER_ID", "user-demo"),
    base_url=os.environ.get("KYNARA_BASE_URL", "http://localhost:8000"),
    fail_closed=True,
)
set_current_kynara(kynara)


@permission_required("crm.contacts.read", resource_arg="contact_id",
                    resource_type="crm.contact")
def read_contact(contact_id: str):
    # Pretend this queries the CRM
    return {"id": contact_id, "name": "Dana Marsh", "tier": "enterprise"}


@permission_required("email.send", resource_type="email",
                    resource_attrs=lambda to, subject, body: {
                        "to": to, "subject": subject, "size": len(body),
                    })
def send_email(to: str, subject: str, body: str):
    print(f"[SMTP] → {to}: {subject}")


@permission_required("payments.refund.issue", resource_arg="payment_id",
                    resource_type="payment",
                    resource_attrs=lambda payment_id, amount_cents: {"amount_cents": amount_cents})
def issue_refund(payment_id: str, amount_cents: int):
    print(f"[Stripe] refunded ${amount_cents/100:.2f} on {payment_id}")


def main() -> None:
    # Tool call 1 — should allow
    print(read_contact("c_123"))

    # Tool call 2 — may be allowed or flagged by quiet-hours policy
    try:
        send_email("alex@example.com", "Hello", "Following up on your ticket")
    except PermissionDenied as e:
        print("Email denied:", e.decision.reason)

    # Tool call 3 — a high-value refund should require approval under default policies
    try:
        issue_refund("pay_456", 75_00)
    except ApprovalRequired as e:
        print("Refund pending approval:", e.decision.reason)


if __name__ == "__main__":
    main()
