from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.org import OrgMembership


class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # argon2id hash — None if the user authenticates only via SSO
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # SSO linkage — set when provisioned via SCIM or on first OIDC/SAML login
    external_idp: Mapped[str | None] = mapped_column(String(32), nullable=True)  # okta | saml | ...
    external_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Super admin — cross-org platform administrator
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Profile customisation
    timezone: Mapped[str | None] = mapped_column(String(80), nullable=True)   # IANA tz e.g. "America/New_York"
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    memberships: Mapped[list["OrgMembership"]] = relationship(back_populates="user")
