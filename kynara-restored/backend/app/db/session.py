"""Async SQLAlchemy engine & session.

Sessions are scoped per-request via dependency injection. A ``SET LOCAL`` statement
installs the current ``org_id`` for Postgres row-level security *inside* the connection.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
    # Supabase/pgBouncer transaction-mode pooler does not support prepared statements.
    connect_args={"statement_cache_size": 0},
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def get_session(org_id: Optional[str] = None) -> AsyncIterator[AsyncSession]:
    """Yield a session with RLS GUC installed for this tenant."""
    async with SessionLocal() as session:
        if org_id:
            # Postgres RLS uses current_setting('app.org_id') in policies.
            await session.execute(
                # literal-bind is safe here: org_id is a UUID already validated by pydantic
                # but we still use a parameterized statement.
                _set_local_org_stmt(org_id)
            )
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def _set_local_org_stmt(org_id: str):
    from sqlalchemy import text
    return text("SELECT set_config('app.org_id', :oid, true)").bindparams(oid=org_id)
