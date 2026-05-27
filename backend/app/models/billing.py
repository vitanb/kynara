from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Subscription(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The Stripe Subscription Item ID (si_xxxx) for the decisions metered price;
    # required for stripe.SubscriptionItem.create_usage_record() in the nightly reporter.
    stripe_subscription_item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="trial")
    # trialing | active | past_due | canceled | incomplete | paused
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="trialing")

    seats_included: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    decisions_included: Mapped[int] = mapped_column(Integer, nullable=False, default=100_000)
    # Overage pricing applied for usage beyond included allotment (price per 1k decisions, cents)
    overage_cents_per_1k: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Stamped when a subscription first becomes past_due; cleared on successful payment.
    # enforce_active_subscription() uses this to apply a 7-day grace period before hard-blocking.
    past_due_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageRecord(Base, UUIDPkMixin):
    __tablename__ = "usage_records"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)  # decisions | agents | storage_mb
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # e.g. {"agent_id": "...", "effect": "allow"}
    dims: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Invoice(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "invoices"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # draft|open|paid|void|uncollectible
    hosted_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
