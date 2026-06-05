"""
Kynara MCP Wrapper — policy client (same interface as kynara-proxy/policy.py).

Checks Kynara policy before forwarding tool calls to the upstream MCP server.
Tries the local sidecar first, falls back to the central API.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("kynara.mcp_wrapper.policy")

SIDECAR_URL = os.getenv("KYNARA_SIDECAR_URL", "http://localhost:7070")
API_BASE_URL = os.getenv("KYNARA_API_BASE_URL", "https://app.kynara.io")
API_KEY = os.getenv("KYNARA_API_KEY", "")
FAIL_OPEN = os.getenv("KYNARA_FAIL_OPEN", "false").lower() == "true"


@dataclass
class Decision:
    effect: str            # "allow" | "deny" | "require_approval"
    reason: str
    decision_id: str
    matched_policy_id: str | None = None
    approval_url: str | None = None


async def check(
    agent_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    context: dict[str, Any] | None = None,
    scope: str | None = None,
    fail_open: bool | None = None,
) -> Decision:
    # When the gateway has mapped this tool to a Kynara scope, evaluate against
    # that scope; otherwise fall back to the raw tool name as the action.
    payload = {
        "subject_type": "agent",
        "subject_id": agent_id,
        "action": scope or tool_name,
        "resource": {
            "type": "mcp_tool",
            "id": tool_name,
            "attrs": _safe_attrs(arguments),
        },
        "context": context or {},
    }

    # Try sidecar first
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            r = await client.post(
                f"{SIDECAR_URL}/api/v1/decisions/check", json=payload
            )
            r.raise_for_status()
            return _parse(r.json())
    except Exception as e:
        logger.warning("sidecar.miss: %s", e)

    # Try central API
    if API_KEY:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.post(
                    f"{API_BASE_URL}/api/v1/decisions/check",
                    json=payload,
                    headers={"X-Kynara-Key": API_KEY},
                )
                r.raise_for_status()
                return _parse(r.json())
        except Exception as e:
            logger.warning("central_api.miss: %s", e)

    # Fallback — prefer the per-server fail mode (from gateway config) when
    # provided; otherwise use the wrapper's global KYNARA_FAIL_OPEN default.
    fo = FAIL_OPEN if fail_open is None else fail_open
    if fo:
        return Decision(effect="allow", reason="kynara_unavailable_fail_open",
                        decision_id="fallback_open")
    return Decision(effect="deny", reason="kynara_unavailable_fail_closed",
                    decision_id="fallback_closed")


def _parse(data: dict) -> Decision:
    return Decision(
        effect=data.get("effect", "deny"),
        reason=data.get("reason", ""),
        decision_id=data.get("decision_id", ""),
        matched_policy_id=data.get("matched_policy_id"),
        approval_url=data.get("approval_url"),
    )


def _safe_attrs(arguments: dict) -> dict:
    out = {}
    for k, v in (arguments or {}).items():
        if isinstance(v, str) and len(v) > 256:
            out[k] = v[:256] + "…"
        elif isinstance(v, (dict, list)):
            out[k] = "<nested>"
        else:
            out[k] = v
    return out
