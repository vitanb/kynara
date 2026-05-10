from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class ApiKey(Base, UUIDPkMixin, TimestampMixin):
    """Scoped API keys. Clear-text only surfaced at creation — DB stores the hash + last-4."""

    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_key_hash"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # sha256(secret + pepper); 64 hex chars
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. "sk_live_"

    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=600)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
