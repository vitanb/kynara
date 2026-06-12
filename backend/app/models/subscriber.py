"""Newsletter / waitlist email subscribers captured from the marketing site."""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class NewsletterSubscriber(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    # Where the signup came from: "blog", "quickstart", "langchain", "home", etc.
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
