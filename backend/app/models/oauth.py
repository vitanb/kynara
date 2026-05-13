"""OAuth 2.0 models — clients and short-lived authorization codes."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class OAuthClient(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    redirect_uris: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_scopes: Mapped[str] = mapped_column(Text, nullable=False, default="read")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    client_secret_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OAuthCode(Base, UUIDPkMixin):
    __tablename__ = "oauth_codes"

    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    client_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("oauth_clients.client_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    code_challenge: Mapped[str | None] = mapped_column(String(128), nullable=True)
    code_challenge_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )
