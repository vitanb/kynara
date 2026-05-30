"""Agent-to-agent delegation grants."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class DelegationGrant(Base, UUIDPkMixin, TimestampMixin):
    """A parent agent delegates a subset of its scopes to a child agent.

    Prevents privilege escalation via two guards:
    1. ``delegated_scopes`` must be a subset of the parent's actual scopes
       (enforced at creation time by the API).
    2. ``chain_depth`` tracks how many hops from the root agent this grant is;
       it cannot exceed ``max_chain_depth``.
    """

    __tablename__ = "delegation_grants"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    parent_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    child_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Scopes being delegated — must be a subset of the parent's actual scopes
    delegated_scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Depth guards — prevents recursive privilege escalation
    max_chain_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chain_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
