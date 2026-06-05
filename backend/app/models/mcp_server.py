"""SQLAlchemy models for the MCP authorization gateway.

A ``McpServer`` is an upstream Model Context Protocol server registered with
Kynara. The Kynara MCP wrapper sits in front of it and enforces policy on every
tool call. Each tool the upstream exposes is recorded as a ``McpTool`` and mapped
to a Kynara capability scope, so the existing RBAC/ABAC policy engine governs
which agents may invoke which tools (least privilege, per call).
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class McpServer(Base, UUIDPkMixin, TimestampMixin):
    """An upstream MCP server fronted by the Kynara gateway."""

    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_mcp_server_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # "sse" | "http" | "stdio"
    transport: Mapped[str] = mapped_column(String(16), nullable=False, default="sse")
    # Upstream endpoint for sse/http transports.
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Command for stdio transport (e.g. "npx -y @modelcontextprotocol/server-foo").
    stdio_cmd: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Headers the wrapper sends to the upstream (e.g. upstream auth token).
    # NOTE: sensitive — should be stored encrypted at rest in production.
    upstream_headers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Scope namespace used when auto-mapping discovered tools → Kynara scopes.
    # e.g. "mcp.crm" → tool "contacts.read" maps to scope "mcp.crm.contacts.read".
    scope_prefix: Mapped[str] = mapped_column(String(128), nullable=False, default="mcp")

    # "closed" (deny on engine error) | "open" (allow on engine error).
    fail_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="closed")

    # When true, tools default to require_approval until explicitly mapped.
    require_approval_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Discovery bookkeeping.
    last_synced_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    tools: Mapped[list["McpTool"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class McpTool(Base, UUIDPkMixin, TimestampMixin):
    """A tool exposed by an upstream MCP server, mapped to a Kynara scope."""

    __tablename__ = "mcp_tools"
    __table_args__ = (UniqueConstraint("server_id", "name", name="uq_mcp_tool_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Tool name as advertised by the upstream MCP server.
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Kynara capability scope this tool requires (the `action` passed to decide()).
    scope: Mapped[str] = mapped_column(String(256), nullable=False)

    # low | medium | high | critical — surfaced in approval prompts and analytics.
    risk_class: Mapped[str] = mapped_column(String(16), nullable=False, default="low")

    # Optional hard override applied before policy: "deny" | "require_approval" | null.
    effect_override: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # When false the wrapper never advertises or forwards this tool.
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    server: Mapped["McpServer"] = relationship(back_populates="tools")
