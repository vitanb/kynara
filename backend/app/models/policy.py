from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Role(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_role_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # `system` roles are created by migrations (e.g. built-in `admin`) and cannot be deleted.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete"
    )


class RolePermission(Base, UUIDPkMixin, TimestampMixin):
    """Grants a scope to a role. Wildcards: ``*`` (any), ``crm.*`` (any under crm)."""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "scope", name="uq_role_scope"),)

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(128), nullable=False)

    role: Mapped[Role] = relationship(back_populates="permissions")


class Policy(Base, UUIDPkMixin, TimestampMixin):
    """An ABAC rule.

    The engine evaluates bound policies in priority order, first matching decision wins.
    A policy's ``condition`` is a JSON expression evaluated against:
      { subject: {id, type, attrs}, action, resource: {type, id, attrs}, context: {time, ip, ...} }

    Effects: ``allow`` | ``deny`` | ``require_approval``.
    """

    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_policy_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    effect: Mapped[str] = mapped_column(
        Enum("allow", "deny", "require_approval", name="policy_effect_enum"),
        nullable=False,
    )
    # Lower numbers evaluated first. Built-in defaults sit at 1000; user policies at 500.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=500)

    # Actions this policy is about. Supports wildcards. Empty → all actions.
    actions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Resource type match (e.g. "crm.contact"). Empty → all resources.
    resource_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Condition AST (see policy/engine.py for grammar)
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PolicyBinding(Base, UUIDPkMixin, TimestampMixin):
    """Links a policy to a subject scope (agent, user, role, or ``*`` for org-wide)."""

    __tablename__ = "policy_bindings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    # Subject selector: "agent:<uuid>", "user:<uuid>", "role:<slug>", "*"
    subject_selector: Mapped[str] = mapped_column(String(128), nullable=False)
