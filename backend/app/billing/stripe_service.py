"""Stripe integration: customers, subscriptions, usage metering, webhooks.

Usage-based billing is wired as follows:
  * Each policy decision increments ``usage_records`` with metric ``decisions``.
  * A nightly aggregator sums the day's decisions and reports them to Stripe via the
    ``subscription_item.usage_records`` API for an included-overage model.
  * Invoice webhooks flip subscription status (past_due, canceled, ...) which directly
    affects the hard-gate check in the policy service (``org is past_due → deny``).
"""
from __future__ import annotations

import hmac
import logging
import time
from hashlib import sha256
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("billing.stripe")

try:
    import stripe  # type: ignore
except ImportError:
    stripe = None  # type: ignore


def _ensure_configured() -> None:
    s = get_settings()
    if not s.stripe_secret_key or stripe is None:
        raise RuntimeError("Stripe not configured")
    stripe.api_key = s.stripe_secret_key


def create_checkout_session(*, org_id: str, plan: str, success_url: str, cancel_url: str) -> str:
    _ensure_configured()
    session = stripe.checkout.Session.create(  # type: ignore
        mode="subscription",
        line_items=[{"price": _price_for_plan(plan), "quantity": 1}],
        metadata={"org_id": org_id, "plan": plan},
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=org_id,
        allow_promotion_codes=True,
    )
    return session.url


def _price_for_plan(plan: str) -> str:
    """Look up the Stripe Price ID for a plan.

    Price IDs come from environment variables so you can swap them without a
    code deploy. Set them in Railway → Variables.

    Frontend sends: "pro" or "enterprise"
    To find your Price ID: Stripe Dashboard → Products → your product → Pricing.
    It looks like:  price_1OxxxxxxxxxxxxxxxxxxxxXX
    """
    s = get_settings()
    mapping = {
        "pro":        s.stripe_price_pro,
        "enterprise": s.stripe_price_enterprise,
        # Legacy aliases — kept for any existing integrations
        "team":       s.stripe_price_team,
        "business":   s.stripe_price_business,
    }
    if plan not in mapping:
        raise ValueError(f"Unknown plan: {plan!r}. Valid plans: {list(mapping)}")
    price_id = mapping[plan]
    # Catch the case where the operator forgot to set the env var
    if not price_id.startswith("price_"):
        raise RuntimeError(
            f"STRIPE_PRICE_{plan.upper()} is not set to a real Stripe Price ID. "
            f"Current value: {price_id!r}. Set it in Railway → Variables."
        )
    return price_id


def create_portal_session(*, customer_id: str, return_url: str) -> str:
    _ensure_configured()
    session = stripe.billing_portal.Session.create(  # type: ignore
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def report_usage(subscription_item_id: str, quantity: int, ts: int | None = None) -> None:
    _ensure_configured()
    stripe.SubscriptionItem.create_usage_record(  # type: ignore
        subscription_item_id,
        quantity=quantity,
        timestamp=ts or int(time.time()),
        action="increment",
    )


def verify_webhook(payload: bytes, sig_header: str) -> dict[str, Any]:
    s = get_settings()
    if not s.stripe_webhook_secret:
        raise RuntimeError("Stripe webhook secret not configured")
    # Equivalent of stripe.Webhook.construct_event, without requiring the library
    parts = dict(kv.split("=", 1) for kv in sig_header.split(","))
    ts = parts["t"]
    sig = parts["v1"]
    signed = f"{ts}.{payload.decode()}".encode()
    mac = hmac.new(s.stripe_webhook_secret.encode(), signed, sha256).hexdigest()
    if not hmac.compare_digest(mac, sig):
        raise PermissionError("invalid Stripe signature")
    import json
    return json.loads(payload)
