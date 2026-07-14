#!/usr/bin/env python3
"""
Kynara demo — Slack support agent tries to refund a customer,
Kynara requires manager approval before the money moves.

Flow:
  1. The agent attempts a $89.00 refund (a money-moving action).
  2. Kynara evaluates the policy and returns `require_approval`.
  3. The agent PAUSES and surfaces an approval request.
  4. A manager approves (in the Kynara UI / Slack); this script polls until resolved.
  5. On approval the refund actually executes; on rejection it's escalated.

Run against a live Kynara:
    export KYNARA_API_BASE_URL="https://kynaraai.com"
    export KYNARA_API_KEY="sk_live_..."
    export KYNARA_AGENT_ID="<your slack-support-agent id>"
    python demo.py

Run offline (no server needed — simulates the approval loop):
    python demo.py --mock
"""
from __future__ import annotations

import os
import sys
import time
import json

BASE = os.getenv("KYNARA_API_BASE_URL", "https://kynaraai.com").rstrip("/")
API_KEY = os.getenv("KYNARA_API_KEY", "")
AGENT_ID = os.getenv("KYNARA_AGENT_ID", "slack-support-agent")
MOCK = "--mock" in sys.argv or not API_KEY

# The refund the Slack agent wants to make.
REFUND = {
    "customer": "cus_dana",
    "order": "#4471",
    "amount_cents": 8900,          # $89.00 — over the $50 approval threshold
    "reason": "duplicate charge",
}


def log(icon: str, msg: str) -> None:
    print(f"  {icon}  {msg}")


def check_decision() -> dict:
    """Ask Kynara whether the agent may issue this refund."""
    payload = {
        "subject_type": "agent",
        "subject_id": AGENT_ID,
        "action": "payments.refund.issue",
        "resource": {
            "type": "payment",
            "id": "pay_8842",
            "attrs": {"amount_cents": REFUND["amount_cents"], "customer": REFUND["customer"]},
        },
        "context": {"channel": "support", "reason": REFUND["reason"]},
    }
    if MOCK:
        # Policy: refunds over $50 -> require_approval
        if REFUND["amount_cents"] > 5000:
            return {"effect": "require_approval", "approval_id": "apr_demo_001",
                    "reason": "policy 'Refunds over $50 need manager approval' matched"}
        return {"effect": "allow", "reason": "under threshold"}

    import requests
    r = requests.post(
        f"{BASE}/api/v1/decisions/check",
        headers={"X-Kynara-Key": API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=10,
    )
    r.raise_for_status()
    return r.json()


def poll_approval(approval_id: str, timeout_s: int = 300) -> str:
    """Wait for a manager to approve or reject. Returns 'approved' | 'rejected'."""
    if MOCK:
        # Simulate a manager taking a few seconds, then approving.
        # Set DEMO_REJECT=1 to see the rejection branch.
        for i in range(3):
            log("⏳", f"waiting for manager… ({i+1}/3)")
            time.sleep(1)
        return "rejected" if os.getenv("DEMO_REJECT") == "1" else "approved"

    import requests
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(
            f"{BASE}/api/v1/approvals/{approval_id}",
            headers={"X-Kynara-Key": API_KEY}, timeout=10,
        )
        r.raise_for_status()
        status = r.json().get("status", "pending")
        if status in ("approved", "rejected"):
            return status
        log("⏳", "still pending — approve it in the Kynara UI or Slack…")
        time.sleep(3)
    return "rejected"  # timed out -> fail closed


def execute_refund() -> None:
    """The real side effect — only reached after approval."""
    log("💸", f"Refund executed: ${REFUND['amount_cents']/100:.2f} to {REFUND['customer']} (order {REFUND['order']})")
    # e.g. stripe.Refund.create(payment_intent="pay_8842", amount=REFUND["amount_cents"])


def main() -> None:
    mode = "MOCK (offline)" if MOCK else f"LIVE → {BASE}"
    print(f"\nKynara refund-approval demo  [{mode}]\n" + "-" * 48)
    print("Customer (Dana): \"I was double-charged $89.00 — please refund the duplicate.\"")
    log("🤖", "Support Agent: issuing the $89.00 refund now…")
    log("🔐", "Agent → Kynara: check payments.refund.issue ($89.00)")

    decision = check_decision()
    effect = decision.get("effect")

    if effect == "allow":
        log("✅", "Kynara: ALLOW — under threshold.")
        execute_refund()
        return

    if effect == "deny":
        log("⛔", f"Kynara: DENY — {decision.get('reason')}. Refund blocked.")
        return

    if effect == "require_approval":
        log("⏸", f"Kynara: REQUIRE_APPROVAL — {decision.get('reason')}")
        log("🤖", "Support Agent (to customer): \"This needs a quick manager sign-off — one moment.\"")
        approval_id = decision.get("approval_id", "apr_unknown")
        log("📨", f"Approval request created: {approval_id}")

        outcome = poll_approval(approval_id)
        if outcome == "approved":
            log("✅", "Manager APPROVED.")
            execute_refund()
            log("🤖", "Support Agent: \"All set, Dana — your $89.00 refund is processed. 3–5 business days.\"")
        else:
            log("🛑", "Manager REJECTED — refund NOT executed.")
            log("🤖", "Support Agent: \"I've escalated your refund to a human teammate who'll follow up.\"")
        return

    log("❓", f"Unexpected effect: {effect!r}")


if __name__ == "__main__":
    main()
