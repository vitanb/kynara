from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    pass


class Tool(Base, UUIDPkMixin, TimestampMixin):
    """A callable capability an agent may invoke (CRM.read, Email.send, DB.query, etc.).

    Tools declare their *required capability scopes*. When an agent invokes the tool via
    the SDK, Kynara resolves whether the current subject has a permission covering every
    required scope.
    """

    __tablename__ = "tools"
    __table_args__ = (UniqueConstraint("organization_id", "namespace", "name", name="uq_tool"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    namespace: Mapped[str] = mapped_column(String(64), nullable=False)   # "crm", "email", "db"
    name: Mapped[str] = mapped_column(String(128), nullable=False)       # "contacts.read"
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Plain English summary of what this tool does — surfaced in approval prompts
    risk_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="low"
    )  # low | medium | high | critical

    # JSON schema describing call arguments. Used to validate SDK calls.
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Toggle for org-wide disable without changing policies
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    scopes: Mapped[list["ToolScope"]] = relationship(back_populates="tool", cascade="all, delete")


class ToolScope(Base, UUIDPkMixin, TimestampMixin):
    """A single capability a tool requires. e.g. ``crm.contacts.read``."""

    __tablename__ = "tool_scopes"
    __table_args__ = (UniqueConstraint("tool_id", "scope", name="uq_tool_scope"),)

    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(128), nullable=False)

    tool: Mapped[Tool] = relationship(back_populates="scopes")
