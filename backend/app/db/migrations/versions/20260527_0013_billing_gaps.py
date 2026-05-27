"""Billing gaps: past_due_since grace period + Stripe subscription item tracking.

Revision ID: 20260527_0013
Revises: 20260505_0012
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260527_0013"
down_revision = "20260505_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # When a subscription first becomes past_due, stamp the moment here.
    # enforce_active_subscription() uses it to apply a 7-day grace period
    # before hard-blocking agents — gives the customer time to fix payment
    # without an immediate service outage.
    op.add_column(
        "subscriptions",
        sa.Column("past_due_since", sa.DateTime(timezone=True), nullable=True),
    )

    # The Stripe Subscription Item ID (si_xxxx) for the decisions metered price.
    # Required for stripe.SubscriptionItem.create_usage_record() in the nightly
    # overage reporter.  Populated from the checkout.session.completed webhook
    # by inspecting line_items.  Null until the customer has a paid subscription.
    op.add_column(
        "subscriptions",
        sa.Column("stripe_subscription_item_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "stripe_subscription_item_id")
    op.drop_column("subscriptions", "past_due_since")
