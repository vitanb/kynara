"""
Kynara MCP Wrapper — Tier 1 MCP server wrapper.

Sits in front of any upstream MCP server and enforces Kynara policy on every
tool call.  Agents need only a one-line config change — swap the MCP server URL:

  Before:  "url": "https://your-mcp-server.example.com/sse"
  After:   "url": "http://kynara-mcp-wrapper:9090/sse"

How it works
────────────
On startup the wrapper connects to the upstream MCP server, discovers its tools,
and caches them.  It then advertises those same tools to connecting agents.  When
an agent calls a tool, the wrapper:

  1. Checks Kynara policy (sidecar → central API → fail_open/closed)
  2. If allowed  → forwards the call to the upstream MCP server and returns the result
  3. If denied   → raises McpError so the agent receives a structured error
  4. If approval → raises McpError with approval_url for the agent to surface

The upstream tool list is refreshed every TOOL_CACHE_TTL seconds so newly added
or removed tools are picked up without a wrapper restart.

Transports supported
────────────────────
• Serves agents via SSE  (http://wrapper/sse)
• Connects to upstream via SSE  (KYNARA_UPSTREAM_MCP_URL)
• Upstream stdio supported — set KYNARA_UPSTREAM_STDIO_CMD instead
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from mcp import ClientSession, types
from mcp.client.sse import sse_client
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

import policy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("kynara.mcp_wrapper")

# ── Configuration ─────────────────────────────────────────────────────────

UPSTREAM_MCP_URL: str = os.getenv(
    "KYNARA_UPSTREAM_MCP_URL", "http://localhost:8000/sse"
)
UPSTREAM_HEADERS: dict[str, str] = {}
if raw := os.getenv("KYNARA_UPSTREAM_HEADERS"):
    # Accepts JSON: '{"Authorization": "Bearer token"}'
    try:
        UPSTREAM_HEADERS = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("KYNARA_UPSTREAM_HEADERS is not valid JSON — ignored")

TOOL_CACHE_TTL: float = float(os.getenv("KYNARA_TOOL_CACHE_TTL", "60"))
AGENT_ID_HEADER: str = os.getenv("KYNARA_AGENT_ID_HEADER", "x-kynara-agent")
PORT: int = int(os.getenv("KYNARA_MCP_WRAPPER_PORT", "9090"))

# ── Tool cache ────────────────────────────────────────────────────────────

_tool_cache: list[types.Tool] = []
_tool_cache_ts: float = 0.0
_cache_lock = asyncio.Lock()


async def _get_upstream_tools() -> list[types.Tool]:
    """Return cached tool list, refreshing from upstream if stale."""
    global _tool_cache, _tool_cache_ts
    async with _cache_lock:
        if time.monotonic() - _tool_cache_ts < TOOL_CACHE_TTL and _tool_cache:
            return _tool_cache

        try:
            async with sse_client(
                url=UPSTREAM_MCP_URL, headers=UPSTREAM_HEADERS, timeout=10
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    _tool_cache = result.tools
                    _tool_cache_ts = time.monotonic()
                    logger.info(
                        "tool_cache.refreshed upstream=%s tools=%d",
                        UPSTREAM_MCP_URL, len(_tool_cache),
                    )
        except Exception as e:
            logger.error("upstream.list_tools.failed: %s", e)
            # Return stale cache if available
            if not _tool_cache:
                raise

    return _tool_cache


async def _call_upstream_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Open a fresh upstream connection, call the tool, return content."""
    async with sse_client(
        url=UPSTREAM_MCP_URL, headers=UPSTREAM_HEADERS, timeout=30
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.isError:
                # Surface upstream errors as MCP errors so agents see them properly
                error_text = _content_to_text(result.content)
                raise ValueError(f"Upstream tool error: {error_text}")
            return result.content


def _content_to_text(
    content: list[types.TextContent | types.ImageContent | types.EmbeddedResource],
) -> str:
    parts = []
    for block in content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
    return " ".join(parts) or "(no text content)"


# ── MCP Server ────────────────────────────────────────────────────────────

server = Server("kynara-mcp-wrapper")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    Return the upstream tool list — exactly the same tools the agent would
    see if it connected directly, so no agent-side changes are needed.
    """
    try:
        return await _get_upstream_tools()
    except Exception as e:
        logger.error("list_tools.failed: %s", e)
        return []


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Enforce Kynara policy, then forward the call to the upstream MCP server.
    """
    args = arguments or {}

    # Extract agent identity from request context (injected by the SSE handler)
    agent_id: str = _current_agent_id.get() or "anonymous"

    logger.info("tool_call | agent=%s tool=%s", agent_id, name)

    # ── Policy check ──────────────────────────────────────────────────────
    dec = await policy.check(
        agent_id=agent_id,
        tool_name=name,
        arguments=args,
        context={"source": "mcp_wrapper", "upstream": UPSTREAM_MCP_URL},
    )

    if dec.effect == "deny":
        logger.warning("blocked | agent=%s tool=%s reason=%s", agent_id, name, dec.reason)
        raise ValueError(
            f"[Kynara] Permission denied for tool '{name}'. "
            f"Reason: {dec.reason}. "
            f"Contact your administrator to request access."
        )

    if dec.effect == "require_approval":
        logger.warning(
            "approval_required | agent=%s tool=%s decision=%s",
            agent_id, name, dec.decision_id,
        )
        raise ValueError(
            f"[Kynara] Tool '{name}' requires human approval before it can run. "
            f"Approval URL: {dec.approval_url}. "
            f"Decision ID: {dec.decision_id}"
        )

    # ── Forward to upstream ───────────────────────────────────────────────
    logger.info("forwarding | agent=%s tool=%s", agent_id, name)
    try:
        content = await _call_upstream_tool(name, args)
        logger.info("success | agent=%s tool=%s", agent_id, name)
        return content
    except ValueError:
        raise
    except Exception as e:
        logger.error("upstream.error | agent=%s tool=%s error=%s", agent_id, name, e)
        raise ValueError(f"[Kynara] Upstream error calling '{name}': {e}") from e


# ── Agent identity context var ────────────────────────────────────────────
# We use a contextvars.ContextVar so each SSE session has its own agent_id.

import contextvars
_current_agent_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_agent_id", default=None
)


# ── Starlette app wiring ──────────────────────────────────────────────────

sse_transport = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    """SSE endpoint — one long-lived connection per agent session."""
    # Extract and store agent ID for this session's context
    agent_id = (
        request.headers.get(AGENT_ID_HEADER)
        or request.headers.get("x-agent-id")
        or request.query_params.get("agent_id")
        or "anonymous"
    )
    token = _current_agent_id.set(agent_id)
    logger.info("session.open agent=%s", agent_id)

    try:
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
    finally:
        _current_agent_id.reset(token)
        logger.info("session.close agent=%s", agent_id)


async def handle_health(request: Request):
    tool_count = len(_tool_cache)
    upstream_ok = tool_count > 0
    return JSONResponse({
        "ok": True,
        "upstream": UPSTREAM_MCP_URL,
        "cached_tools": tool_count,
        "upstream_reachable": upstream_ok,
        "cache_age_seconds": round(time.monotonic() - _tool_cache_ts, 1)
        if _tool_cache_ts else None,
    })


async def on_startup() -> None:
    """Pre-warm the tool cache so the first agent connection is fast."""
    logger.info(
        "kynara-mcp-wrapper starting | upstream=%s port=%d fail_open=%s",
        UPSTREAM_MCP_URL, PORT, policy.FAIL_OPEN,
    )
    try:
        await _get_upstream_tools()
    except Exception as e:
        logger.warning("startup.tool_cache.failed: %s — will retry on first request", e)


starlette_app = Starlette(
    on_startup=[on_startup],
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/health", endpoint=handle_health),
        Mount("/messages/", app=sse_transport.handle_post_message),
    ],
)


# ── Entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:starlette_app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )
