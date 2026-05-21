"""
Kynara Proxy — local audit logger.

Appends one JSON line per decision to an append-only JSONL file.
The central sidecar also streams decisions back to the Kynara API
audit trail, so this is a local redundant copy for ops/debugging.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from policy import Decision

logger = logging.getLogger("kynara.proxy.audit")

# Ensure the log file directory exists
Path(settings.audit_log_path).parent.mkdir(parents=True, exist_ok=True)


def log_decision(
    *,
    agent_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    decision: Decision,
    path: str,
    method: str,
    upstream_status: int | None = None,
) -> None:
    """Append one audit record to the local JSONL file."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision_id": decision.decision_id,
        "agent_id": agent_id,
        "tool_name": tool_name,
        "effect": decision.effect,
        "reason": decision.reason,
        "matched_policy_id": decision.matched_policy_id,
        "http_path": path,
        "http_method": method,
        "upstream_status": upstream_status,
        # Truncated args — full payload stays in Kynara central audit
        "arguments_preview": {
            k: (str(v)[:80] if isinstance(v, str) else type(v).__name__)
            for k, v in (arguments or {}).items()
        },
    }
    try:
        with open(settings.audit_log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:
        logger.warning("audit.write_failed: %s", e)


def log_passthrough(*, path: str, method: str, agent_id: str, reason: str) -> None:
    """Log requests that had no tool calls (plain LLM calls, health checks, etc.)."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision_id": None,
        "agent_id": agent_id,
        "tool_name": None,
        "effect": "passthrough",
        "reason": reason,
        "http_path": path,
        "http_method": method,
        "upstream_status": None,
    }
    try:
        with open(settings.audit_log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass
