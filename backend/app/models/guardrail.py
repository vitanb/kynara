"""SQLAlchemy models for guardrail integrations and events."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class GuardrailIntegration(Base):
    __tablename__ = "guardrail_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_endpoint: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    default_action: Mapped[str] = mapped_column(
        String(80), nullable=False, default="alert_only")
    # {"critical": "suspend_agent", "warning": "alert_only"}
    severity_action_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # null = all agents; list of UUIDs = specific agents
    agent_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    # null = all rules; list of strings = specific rule names
    monitored_rules: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False)


class GuardrailEvent(Base):
    __tablename__ = "guardrail_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardrail_integrations.id", ondelete="SET NULL"), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    rule_name: Mapped[str] = mapped_column(String(400), nullable=False)
    severity: Mapped[str] = mapped_column(String(80), nullable=False, default="warning")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    action_taken: Mapped[str] = mapped_column(String(80), nullable=False)
    action_detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class GuardrailRule(Base):
    """Threshold-based auto-revocation rule.

    When the number of matching guardrail events for an agent exceeds
    ``event_count_threshold`` within the last ``time_window_seconds``,
    ``action`` is enforced automatically.

    Filters (filter_agent_ids, filter_severities, filter_rule_names) are all
    optional — null means "match anything".
    """
    __tablename__ = "guardrail_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True)
    # null = applies to all integrations in the org
    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardrail_integrations.id", ondelete="CASCADE"),
        nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Threshold condition
    event_count_threshold: Mapped[int] = mapped_column(default=1)
    time_window_seconds: Mapped[int] = mapped_column(default=300)

    # Optional filters — null = match anything
    filter_agent_ids: Mapped[list | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True)
    filter_severities: Mapped[list | None] = mapped_column(
        ARRAY(String), nullable=True)
    filter_rule_names: Mapped[list | None] = mapped_column(
        ARRAY(String), nullable=True)

    action: Mapped[str] = mapped_column(String(80), nullable=False, default="alert_only")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False)
