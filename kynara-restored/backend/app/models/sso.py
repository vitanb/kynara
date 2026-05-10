from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class SsoConnection(Base, UUIDPkMixin, TimestampMixin):
    """A configured identity provider for an organization."""

    __tablename__ = "sso_connections"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_sso_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol: Mapped[str] = mapped_column(
        Enum("oidc", "saml", name="sso_protocol_enum"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # OIDC fields
    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # client_secret is stored encrypted at rest by app layer (AES-GCM with KMS DEK)
    client_secret_enc: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # SAML fields
    idp_entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idp_sso_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    idp_x509_cert: Mapped[str | None] = mapped_column(String(8192), nullable=True)

    # Map IdP attributes to Kynara user fields, e.g. {"email": "email", "name": "displayName"}
    attribute_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # When set, only users with @ one of these domains may use this connection
    email_domain_allowlist: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enforce_for_org: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # If True, password logins for this org's members are disabled.


class ScimSync(Base, UUIDPkMixin, TimestampMixin):
    """Tracks SCIM 2.0 user/group provisioning events."""

    __tablename__ = "scim_syncs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)  # User | Group
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
