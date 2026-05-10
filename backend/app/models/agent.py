from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Agent(Base, UUIDPkMixin, TimestampMixin):
    """An AI agent registered for an org. Every tool call it makes flows through Kynara."""

    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_agent_slug_per_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # `human_supervised` requires approval for elevated actions; `autonomous` runs without it.
    mode: Mapped[str] = mapped_column(
        Enum("human_supervised", "autonomous", "read_only", name="agent_mode_enum"),
        nullable=False,
        default="human_supervised",
    )

    # Model + runtime metadata
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)  # e.g. "claude-sonnet-4-6"
    runtime_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Kill-switch. Agents with `is_active=False` are denied all actions.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Daily action budget (rate-limit safeguard at the agent level)
    daily_action_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)

    # Approval escalation policy
    escalation_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True
    )

    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Risk classification (human-assigned or inferred from tool registry)
    risk_class: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="agent_risk_class_enum"),
        nullable=False,
        default="medium",
    )

    # Computed risk score 0–100 — updated by the anomaly detector cron and on agent writes.
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class AgentAssignment(Base, UUIDPkMixin, TimestampMixin):
    """Binds an agent to the user it acts on behalf of.

    An agent may be assigned to multiple users (e.g., a shared 'CRM Assistant' serving a team),
    but each action is evaluated against *one* active assignment so accountability is unambiguous.
    """

    __tablename__ = "agent_assignments"
    __table_args__ = (
        UniqueConstraint("agent_id", "user_id", "organization_id", name="uq_agent_assignment"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Caps the permission set to at most the intersection of (user_grants, role_grants)
    role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))
    # Time-boxed delegation is a *must-have* for agents
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
