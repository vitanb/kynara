"""Public newsletter subscribe endpoint — no auth required."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.subscriber import NewsletterSubscriber

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscribe", tags=["subscribe"])


async def _session():
    async with SessionLocal() as s:
        yield s


class SubscribeIn(BaseModel):
    email: EmailStr
    source: str | None = Field(default=None, max_length=64)


@router.post("")
async def subscribe(body: SubscribeIn, session: AsyncSession = Depends(_session)):
    """Capture a newsletter/waitlist signup. Idempotent on email."""
    email = str(body.email).strip().lower()
    existing = await session.scalar(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )
    if existing is None:
        session.add(NewsletterSubscriber(email=email, source=(body.source or None)))
        await session.commit()
        logger.info("newsletter.subscribed email=%s source=%s", email, body.source)
    return {"ok": True}
