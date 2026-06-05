"""Minimal Okta API client for agent-identity sync.

Uses SSWS API-token auth. Supports two discovery modes:
  • "agents" — Okta first-class agent identities (GET /api/v1/agents)
  • "group"  — members of a designated Okta group (GET /api/v1/groups/{id}/users)

Responses are normalized to a stable shape:
  {"external_id", "display_name", "login", "status", "groups": [<name>...]}
"""
from __future__ import annotations

import re
from typing import Any

import httpx


def normalize_identity(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Okta agent/user object to Kynara's stable identity shape.

    Defensive about field names so it works across Okta's agent and user schemas.
    """
    profile = raw.get("profile") or {}
    ext_id = str(raw.get("id") or raw.get("agentId") or profile.get("id") or "").strip()

    name = (
        profile.get("displayName")
        or profile.get("name")
        or raw.get("name")
        or raw.get("label")
        or " ".join(p for p in [profile.get("firstName"), profile.get("lastName")] if p).strip()
        or profile.get("login")
        or profile.get("email")
        or ext_id
    )
    login = profile.get("login") or profile.get("email") or raw.get("name") or ext_id
    return {
        "external_id": ext_id,
        "display_name": (name or ext_id)[:255],
        "login": login,
        "status": raw.get("status"),
        "groups": [],  # populated separately via groups_for()
    }


def _next_link(headers: httpx.Headers) -> str | None:
    """Parse Okta's RFC-5988 Link header for the rel=next page URL."""
    link = headers.get("link") or headers.get("Link")
    if not link:
        return None
    for part in link.split(","):
        m = re.search(r'<([^>]+)>\s*;\s*rel="next"', part)
        if m:
            return m.group(1)
    return None


class OktaClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"SSWS {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _get_all(self, url: str, params: dict | None = None) -> list[dict]:
        """GET a collection, following Okta Link pagination."""
        out: list[dict] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params, headers=self._headers())
            r.raise_for_status()
            out.extend(r.json() or [])
            nxt = _next_link(r.headers)
            # Bounded pagination to avoid runaway loops.
            for _ in range(50):
                if not nxt:
                    break
                r = await client.get(nxt, headers=self._headers())
                r.raise_for_status()
                out.extend(r.json() or [])
                nxt = _next_link(r.headers)
        return out

    async def test(self) -> dict:
        """Verify connectivity + token. Returns basic org info."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base}/api/v1/org", headers=self._headers())
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "org": data.get("companyName") or data.get("subdomain"),
                    "status": data.get("status")}

    async def list_identities(self, sync_mode: str, group_id: str | None) -> list[dict]:
        if sync_mode == "group":
            if not group_id:
                raise ValueError("group_id is required for group sync mode")
            raw = await self._get_all(f"{self.base}/api/v1/groups/{group_id}/users")
        else:  # "agents"
            raw = await self._get_all(f"{self.base}/api/v1/agents")
        return [normalize_identity(x) for x in raw if x]

    async def groups_for(self, external_id: str) -> list[str]:
        """Group names the identity belongs to (for role mapping)."""
        try:
            raw = await self._get_all(f"{self.base}/api/v1/users/{external_id}/groups")
        except Exception:
            return []
        names = []
        for g in raw:
            prof = g.get("profile") or {}
            n = prof.get("name") or g.get("name")
            if n:
                names.append(n)
        return names


def role_for_groups(groups: list[str], role_mapping: dict[str, str]) -> str | None:
    """First Okta group (in mapping insertion order) that maps to a Kynara role slug."""
    for okta_group, role_slug in (role_mapping or {}).items():
        if okta_group in groups:
            return role_slug
    return None
