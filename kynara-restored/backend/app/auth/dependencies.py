"""FastAPI auth dependencies."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import decode_access_token
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ApiKey, OrgMembership, User


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    org_id: str
    seat_role: str
    scopes: tuple[str, ...]
    auth_method: str  # "jwt" | "api_key"
    api_key_id: str | None = None
    is_superadmin: bool = False


async def _get_session():
    async with SessionLocal() as s:
        yield s


async def get_principal(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(_get_session),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer credential")
    credential = authorization.split(" ", 1)[1].strip()

    settings = get_settings()
    if credential.startswith(settings.api_key_prefix):
        h = hashlib.sha256(credential.encode()).hexdigest()
        row = await session.scalar(
            select(ApiKey).where(ApiKey.key_hash == h, ApiKey.revoked.is_(False))
        )
        if not row:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        try:
            row.last_used_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception:
            pass
        return Principal(
            user_id=str(row.created_by_user_id),
            org_id=str(row.organization_id),
            seat_role="api_key",
            scopes=tuple(row.scopes or []),
            auth_method="api_key",
            api_key_id=str(row.id),
        )

    try:
        claims = decode_access_token(credential)
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from e

    membership = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.user_id == claims.sub,
            OrgMembership.organization_id == claims.org,
        )
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Org membership revoked")

    user = await session.get(User, claims.sub)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User inactive")

    return Principal(
        user_id=claims.sub,
        org_id=claims.org,
        seat_role=membership.seat_role,
        scopes=tuple(claims.scopes),
        auth_method="jwt",
        is_superadmin=claims.is_superadmin,
    )


def require_seat(*roles: str):
    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.seat_role not in roles and principal.seat_role != "owner":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient seat role")
        return principal
    return _dep


def require_superadmin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return principal
