"""PolicyVersion — immutable snapshot of a policy at a point in time."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPkMixin


class PolicyVersion(Base, UUIDPkMixin):
    """An immutable snapshot of a Policy captured before each update.

    version_number is monotonically increasing per policy (1-based).
    snapshot holds the full serialised policy state at that moment.
    changed_by stores the actor string that triggered the change that
    created this snapshot (i.e. the actor who performed the update after
    which this version became the previous state, or the actor who did a
    rollback).
    """

    __tablename__ = "policy_versions"
    __table_args__ = (
        Index("ix_pv_policy_version", "policy_id", "version_number", unique=True),
        Index("ix_pv_org", "organization_id"),
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 1-based, monotonically increasing per policy
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Full serialised policy state (all mutable columns)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # "user:<uuid>" | "api_key:<uuid>" | "system"
    changed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    # Optional human note (e.g. "rolling back: broke prod traffic")
    change_note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
