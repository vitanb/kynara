from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class ApprovalRequest(Base, UUIDPkMixin, TimestampMixin):
    """A human-approval request created when the policy engine returns require_approval.

    The requesting agent polls GET /approvals/{id}/status to learn the outcome.
    An org owner or admin visits the Approvals page to approve or reject.
    """

    __tablename__ = "approval_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # The agent / user making the request
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id:   Mapped[str] = mapped_column(String(128), nullable=False)
    on_behalf_of_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # What was being attempted
    action:        Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id:   Mapped[str | None] = mapped_column(String(255), nullable=True)
    resource_attrs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    context:       Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    matched_policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Review state
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", "expired",
             name="approval_status_enum", create_type=False),
        nullable=False, default="pending",
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    reviewed_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note:  Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Auto-expire after this time if not acted upon
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
