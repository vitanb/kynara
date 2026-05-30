"""Agent-to-agent delegation scope resolution.

The policy decision engine calls ``get_delegated_scopes()`` when evaluating a
request from an agent that may be acting under a delegation chain.  The returned
scopes are unioned with the agent's directly-assigned scopes before the policy
match is evaluated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delegation_grant import DelegationGrant


async def get_delegated_scopes(
    session: AsyncSession,
    agent_id: str,
    org_id: str,
) -> list[str]:
    """Return all scopes actively delegated TO ``agent_id`` within ``org_id``.

    Only returns scopes from grants that are:
    - ``is_active = True``
    - Not expired (``expires_at`` is null or in the future)
    - Not revoked (``revoked_at`` is null)
    - Belong to the same org

    Scopes from multiple grants are union-merged (deduplicated).
    """
    now = datetime.now(tz=timezone.utc)
    grants = (await session.scalars(
        select(DelegationGrant).where(
            DelegationGrant.organization_id == uuid.UUID(org_id),
            DelegationGrant.child_agent_id == uuid.UUID(agent_id),
            DelegationGrant.is_active.is_(True),
            DelegationGrant.revoked_at.is_(None),
            (DelegationGrant.expires_at.is_(None)) | (DelegationGrant.expires_at > now),
        )
    )).all()

    scopes: set[str] = set()
    for grant in grants:
        scopes.update(grant.delegated_scopes or [])
    return sorted(scopes)


async def validate_delegation(
    session: AsyncSession,
    parent_agent_id: str,
    child_agent_id: str,
    org_id: str,
    requested_scopes: list[str],
    parent_scopes: list[str],
) -> None:
    """Raise ValueError if the delegation request is invalid.

    Checks:
    1. requested_scopes ⊆ parent_scopes (no scope amplification)
    2. child_agent is not the same as parent_agent (no self-delegation)
    3. chain_depth of any existing grants to the parent does not exceed max_chain_depth
    """
    if parent_agent_id == child_agent_id:
        raise ValueError("An agent cannot delegate to itself.")

    invalid = set(requested_scopes) - set(parent_scopes)
    if invalid:
        raise ValueError(
            f"Cannot delegate scopes not held by the parent agent: {sorted(invalid)}"
        )

    # Check chain depth — find the maximum chain_depth of grants TO the parent
    now = datetime.now(tz=timezone.utc)
    parent_grants = (await session.scalars(
        select(DelegationGrant).where(
            DelegationGrant.organization_id == uuid.UUID(org_id),
            DelegationGrant.child_agent_id == uuid.UUID(parent_agent_id),
            DelegationGrant.is_active.is_(True),
            DelegationGrant.revoked_at.is_(None),
            (DelegationGrant.expires_at.is_(None)) | (DelegationGrant.expires_at > now),
        )
    )).all()

    if parent_grants:
        max_existing_depth = max(g.chain_depth for g in parent_grants)
        max_allowed = min(g.max_chain_depth for g in parent_grants)
        if max_existing_depth >= max_allowed:
            raise ValueError(
                f"Delegation chain depth {max_existing_depth} has reached the maximum "
                f"allowed depth of {max_allowed}. Cannot create further delegations."
            )
