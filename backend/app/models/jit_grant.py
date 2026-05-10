"""Time-bound JIT (Just-In-Time) grants for human users.

When a developer needs ``crm:write`` for two hours to debug a production
issue, an admin grants it via the JIT flow. The grant has an expiry; an
authoritative background job at expiry deactivates the grant and writes
``access.elevation.expired`` to the audit chain.

The Principal resolution path (``app.auth.dependencies``) consults active
grants when computing the user's effective scopes.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class JitGrant(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "jit_grants"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # The additional scopes this grant adds. Stored as a string array for
    # easy intersection with the user's role scopes at decision time.
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    justification: Mapped[str] = mapped_column(Text, nullable=False)
    ticket_url: Mapped[str | None] = mapped_column(String(2048))

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
