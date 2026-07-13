"""
Kynara MCP Wrapper — gateway control-plane client.

When KYNARA_MCP_SERVER_ID is set, the wrapper pulls its tool→scope mapping and
per-agent least-privilege tool list from the Kynara backend, so MCP servers are
governed centrally instead of via local env config:

  • get_config()         — tool→scope map + fail mode for this server
  • scope_for_tool()     — the Kynara scope (decision `action`) a tool maps to
  • allowed_tool_names() — the tools a given agent is permitted to see/invoke
  • sync_tools()         — register discovered upstream tools for mapping

If the gateway is not configured (no server id / api key) every function degrades
gracefully and the wrapper falls back to its existing per-call policy check.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger("kynara.mcp_wrapper.gateway")

API_BASE_URL = os.getenv("KYNARA_API_BASE_URL", "https://kynaraai.com")
API_KEY = os.getenv("KYNARA_API_KEY", "")
SERVER_ID = os.getenv("KYNARA_MCP_SERVER_ID", "")
CONFIG_TTL = float(os.getenv("KYNARA_GATEWAY_CONFIG_TTL", "60"))

ENABLED = bool(SERVER_ID and API_KEY)

_config: dict = {}
_config_ts: float = 0.0


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}"}


async def get_config(force: bool = False) -> dict:
    """Fetch (and cache) this server's config + tool→scope map from the backend."""
    global _config, _config_ts
    if not ENABLED:
        return {}
    if not force and _config and (time.monotonic() - _config_ts) < CONFIG_TTL:
        return _config
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{API_BASE_URL}/api/v1/mcp/servers/{SERVER_ID}/config",
                headers=_headers(),
            )
            r.raise_for_status()
            _config = r.json()
            _config_ts = time.monotonic()
            return _config
    except Exception as e:  # noqa: BLE001
        logger.warning("gateway.config.fetch_failed: %s", e)
        return _config  # last-known-good (may be empty)


async def scope_for_tool(tool_name: str) -> str | None:
    """The Kynara scope a tool maps to (passed as `action` to the decision API)."""
    cfg = await get_config()
    tool = (cfg.get("tools") or {}).get(tool_name)
    return tool.get("scope") if tool else None


async def effect_override_for_tool(tool_name: str) -> str | None:
    """A hard effect set by an admin for this tool ("deny" | "require_approval"),
    applied before the policy decision. None means the policy engine decides."""
    cfg = await get_config()
    tool = (cfg.get("tools") or {}).get(tool_name)
    return tool.get("effect_override") if tool else None


async def fail_open() -> bool | None:
    """This server's fail behaviour when the policy engine is unreachable.

    True  → fail-open (allow), False → fail-closed (deny),
    None  → unmanaged: let the wrapper fall back to its KYNARA_FAIL_OPEN default.
    """
    if not ENABLED:
        return None
    cfg = await get_config()
    fm = cfg.get("fail_mode")
    if fm == "open":
        return True
    if fm == "closed":
        return False
    return None


async def allowed_tool_names(agent_id: str) -> set[str] | None:
    """Tool names this agent may see.

    Returns None when filtering should be skipped (gateway disabled, anonymous
    agent, or transient error) — per-call policy enforcement still applies, so
    this is a least-privilege *discovery* optimisation, not the security boundary.
    """
    if not ENABLED or not agent_id or agent_id == "anonymous":
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{API_BASE_URL}/api/v1/mcp/servers/{SERVER_ID}/allowed-tools",
                params={"subject_type": "agent", "subject_id": agent_id},
                headers=_headers(),
            )
            r.raise_for_status()
            data = r.json()
            return {t["name"] for t in data.get("tools", [])}
    except Exception as e:  # noqa: BLE001
        logger.warning("gateway.allowed_tools.failed: %s", e)
        return None


async def sync_tools(tools: list) -> None:
    """Register discovered upstream tools with the backend for scope mapping."""
    if not ENABLED:
        return
    payload = {
        "tools": [
            {
                "name": t.name,
                "description": getattr(t, "description", None),
                "input_schema": getattr(t, "inputSchema", None) or {},
            }
            for t in tools
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{API_BASE_URL}/api/v1/mcp/servers/{SERVER_ID}/tools/sync",
                json=payload, headers=_headers(),
            )
            r.raise_for_status()
            logger.info("gateway.tools_synced: %s", r.json())
    except Exception as e:  # noqa: BLE001
        logger.warning("gateway.sync_tools.failed: %s", e)
