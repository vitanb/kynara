"""Okta → Kynara agent-identity sync.

Idempotently upserts Okta agent identities as Kynara ``Agent`` records (matched
by external_source="okta" + external_id), records Okta provenance, and optionally
maps Okta groups to Kynara roles via a configured on-behalf user.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.idp.okta import OktaClient, role_for_groups
from app.models.agent import Agent, AgentAssignment
from app.models.agent_idp import AgentIdentityProvider
from app.models.policy import Role


def _slugify(s: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:56]
    return base or "agent"


async def _unique_slug(session: AsyncSession, org_id: uuid.UUID, desired: str,
                       keep_agent_id: uuid.UUID | None) -> str:
    """Return a slug unique within the org (suffixing on collision)."""
    slug = desired
    for i in range(0, 1000):
        candidate = slug if i == 0 else f"{slug}-{i}"
        existing = await session.scalar(
            select(Agent).where(Agent.organization_id == org_id, Agent.slug == candidate)
        )
        if existing is None or existing.id == keep_agent_id:
            return candidate
    return f"{slug}-{uuid.uuid4().hex[:6]}"


async def run_sync(session: AsyncSession, provider: AgentIdentityProvider) -> dict:
    stats = {"created": 0, "updated": 0, "role_grants": 0, "deactivated": 0, "errors": []}
    org_id = provider.organization_id

    if not provider.api_token_enc:
        stats["errors"].append("no api token configured")
        provider.last_sync_status = "error"
        provider.last_sync_stats = stats
        provider.last_synced_at = datetime.now(timezone.utc).isoformat()
        await session.commit()
        return stats

    token = decrypt(provider.api_token_enc)
    client = OktaClient(provider.base_url, token)

    try:
        identities = await client.list_identities(provider.sync_mode, provider.group_id)
    except Exception as e:  # noqa: BLE001
        stats["errors"].append(f"list failed: {e}")
        provider.last_sync_status = "error"
        provider.last_sync_stats = stats
        provider.last_synced_at = datetime.now(timezone.utc).isoformat()
        await session.commit()
        return stats

    do_roles = bool(provider.default_on_behalf_user_id and provider.role_mapping)
    seen_ext_ids: set[str] = set()

    for ident in identities:
        ext_id = ident.get("external_id")
        if not ext_id:
            continue
        seen_ext_ids.add(ext_id)
        try:
            agent = await session.scalar(
                select(Agent).where(
                    Agent.organization_id == org_id,
                    Agent.external_source == "okta",
                    Agent.external_id == ext_id,
                )
            )
            groups: list[str] = []
            if do_roles:
                groups = await client.groups_for(ext_id)

            meta = {
                "okta_login": ident.get("login"),
                "okta_status": ident.get("status"),
                "okta_groups": groups,
            }

            if agent is None:
                slug = await _unique_slug(
                    session, org_id, _slugify(ident.get("login") or ident.get("display_name")), None
                )
                agent = Agent(
                    organization_id=org_id, slug=slug,
                    display_name=ident.get("display_name") or ext_id,
                    mode=provider.default_mode, external_source="okta", external_id=ext_id,
                    runtime_metadata=meta, is_active=True,
                )
                session.add(agent)
                await session.flush()
                stats["created"] += 1
            else:
                agent.display_name = ident.get("display_name") or agent.display_name
                agent.runtime_metadata = {**(agent.runtime_metadata or {}), **meta}
                agent.is_active = True
                stats["updated"] += 1

            # Optional role mapping (one role per agent via the on-behalf user).
            if do_roles:
                role_slug = role_for_groups(groups, provider.role_mapping)
                if role_slug:
                    role = await session.scalar(
                        select(Role).where(Role.organization_id == org_id, Role.slug == role_slug)
                    )
                    if role:
                        asg = await session.scalar(
                            select(AgentAssignment).where(
                                AgentAssignment.agent_id == agent.id,
                                AgentAssignment.user_id == provider.default_on_behalf_user_id,
                                AgentAssignment.organization_id == org_id,
                            )
                        )
                        if asg is None:
                            session.add(AgentAssignment(
                                organization_id=org_id, agent_id=agent.id,
                                user_id=provider.default_on_behalf_user_id,
                                role_id=role.id, is_active=True,
                            ))
                        else:
                            asg.role_id = role.id
                            asg.is_active = True
                        stats["role_grants"] += 1
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"{ext_id}: {e}")

    # Deactivate Okta-sourced agents no longer present upstream.
    if provider.deactivate_missing:
        current = (await session.scalars(
            select(Agent).where(
                Agent.organization_id == org_id, Agent.external_source == "okta",
                Agent.is_active.is_(True),
            )
        )).all()
        for a in current:
            if a.external_id not in seen_ext_ids:
                a.is_active = False
                stats["deactivated"] += 1

    provider.last_synced_at = datetime.now(timezone.utc).isoformat()
    provider.last_sync_status = "error" if stats["errors"] else "ok"
    provider.last_sync_stats = stats
    await session.commit()
    return stats
