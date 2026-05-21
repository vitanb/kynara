"""
Kynara Proxy — policy client.

Tries the local sidecar first (sub-millisecond, see sidecar/main.go).
Falls back to the central Kynara API if the sidecar is unreachable.
Respects fail_open / fail_closed setting.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("kynara.proxy.policy")


@dataclass
class Decision:
    effect: str            # "allow" | "deny" | "require_approval"
    reason: str
    decision_id: str
    matched_policy_id: str | None = None
    approval_url: str | None = None
    ttl_seconds: int = 5


async def check(
    agent_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    resource_type: str = "tool",
    context: dict[str, Any] | None = None,
) -> Decision:
    """
    Ask Kynara whether *agent_id* may invoke *tool_name* with *arguments*.

    Resolution order:
      1. Local sidecar  (fastest — uses cached policy bundle)
      2. Central API    (fallback if sidecar unreachable)
      3. fail_open / fail_closed default
    """
    payload = {
        "subject_type": settings.default_subject_type,
        "subject_id": agent_id,
        "action": tool_name,
        "resource": {
            "type": resource_type,
            "id": tool_name,
            "attrs": _safe_attrs(arguments),
        },
        "context": context or {},
    }

    # 1. Try sidecar
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.post(
                f"{settings.sidecar_url}/api/v1/decisions/check",
                json=payload,
            )
            resp.raise_for_status()
            return _parse(resp.json())
    except Exception as e:
        logger.warning("sidecar.unreachable: %s — trying central API", e)

    # 2. Try central API
    if settings.api_key:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"{settings.api_base_url}/api/v1/decisions/check",
                    json=payload,
                    headers={"X-Kynara-Key": settings.api_key},
                )
                resp.raise_for_status()
                return _parse(resp.json())
        except Exception as e:
            logger.warning("central_api.unreachable: %s", e)

    # 3. Fallback
    if settings.fail_open:
        logger.error("kynara.unavailable — failing OPEN (KYNARA_FAIL_OPEN=true)")
        return Decision(
            effect="allow",
            reason="kynara_unavailable_fail_open",
            decision_id="fallback_open",
        )
    else:
        logger.error("kynara.unavailable — failing CLOSED (KYNARA_FAIL_OPEN=false)")
        return Decision(
            effect="deny",
            reason="kynara_unavailable_fail_closed",
            decision_id="fallback_closed",
        )


def _parse(data: dict) -> Decision:
    return Decision(
        effect=data.get("effect", "deny"),
        reason=data.get("reason", ""),
        decision_id=data.get("decision_id", ""),
        matched_policy_id=data.get("matched_policy_id"),
        approval_url=data.get("approval_url"),
        ttl_seconds=data.get("ttl_seconds", 5),
    )


def _safe_attrs(arguments: dict) -> dict:
    """Truncate large argument values so they're safe to log and send."""
    out = {}
    for k, v in (arguments or {}).items():
        if isinstance(v, str) and len(v) > 256:
            out[k] = v[:256] + "…"
        elif isinstance(v, (dict, list)):
            out[k] = "<nested>"
        else:
            out[k] = v
    return out
