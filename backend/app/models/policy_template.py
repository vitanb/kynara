"""PolicyTemplate model — reusable policy definitions for the marketplace."""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class PolicyTemplate(Base, UUIDPkMixin, TimestampMixin):
    """A pre-built policy bundle that orgs can install with one click."""

    __tablename__ = "policy_templates"
    __table_args__ = (UniqueConstraint("slug", name="uq_policy_template_slug"),)

    # e.g. "crm-agent-safe", "code-agent-restricted"
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # "crm" | "code" | "data" | "email" | "general"
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")

    author: Mapped[str] = mapped_column(String(128), nullable=False, default="kynara")

    # Policy definition — same shape as the BundleEnvelope policies list
    template_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    install_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
