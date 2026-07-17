"""Deterministic risk scoring for approval requests.

Used to (a) badge approvals in the console so reviewers triage by risk instead of
arrival order, and (b) power approval-fatigue analytics (are high-risk requests
getting rubber-stamped?).

The score is intentionally rule-based — same inputs, same score — so it can be
explained to an auditor line by line. Factors:

- monetary size (``resource_attrs.amount_cents`` / ``amount``)
- tainted context (untrusted input was present when the agent acted —
  OWASP AI Exchange #LEAST MODEL PRIVILEGE risk elevation)
- action namespace (payments/infra/security/data-egress are inherently riskier)
- bulk markers (``is_bulk_operation``, ``recipient_count``)
"""
from __future__ import annotations

from typing import Any

HIGH_RISK_NAMESPACES = ("payments", "infra", "security", "iam", "db", "deploy")
EGRESS_ACTIONS = ("email.send", "slack.message.send", "http.post", "file.upload")


def score_approval(
    action: str,
    resource_attrs: dict[str, Any] | None,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return ``{"level": "low"|"medium"|"high", "score": int, "factors": [str]}``."""
    attrs = resource_attrs or {}
    ctx = context or {}
    score = 0
    factors: list[str] = []

    # Monetary size
    amount_cents = attrs.get("amount_cents")
    if amount_cents is None and isinstance(attrs.get("amount"), (int, float)):
        amount_cents = float(attrs["amount"]) * 100
    if isinstance(amount_cents, (int, float)):
        if amount_cents >= 100_000:        # >= $1,000
            score += 40
            factors.append(f"amount ${amount_cents / 100:,.0f} (>= $1,000)")
        elif amount_cents >= 25_000:       # >= $250
            score += 25
            factors.append(f"amount ${amount_cents / 100:,.0f} (>= $250)")
        elif amount_cents >= 10_000:       # >= $100
            score += 10
            factors.append(f"amount ${amount_cents / 100:,.0f} (>= $100)")

    # Untrusted input present when the agent acted
    taint = ctx.get("taint")
    trust = str(ctx.get("trust_level", "")).lower()
    if taint or trust in ("untrusted", "low", "tainted"):
        score += 30
        factors.append("tainted context (untrusted input in session)")

    # Inherently risky namespaces
    ns = (action or "").split(".")[0].split(":")[0].lower()
    if ns in HIGH_RISK_NAMESPACES:
        score += 15
        factors.append(f"high-risk namespace '{ns}'")
    if action in EGRESS_ACTIONS:
        score += 15
        factors.append("data-egress action")

    # Bulk operations
    if attrs.get("is_bulk_operation"):
        score += 20
        factors.append("bulk operation")
    rc = attrs.get("recipient_count")
    if isinstance(rc, (int, float)) and rc > 10:
        score += 15
        factors.append(f"{int(rc)} recipients")

    level = "high" if score >= 50 else "medium" if score >= 25 else "low"
    return {"level": level, "score": score, "factors": factors}
