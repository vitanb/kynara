"""
Kynara Proxy — Tier 0 transparent HTTP reverse proxy.

Drop-in replacement for any HTTP-based tool API.  Agents need zero code changes:
just point OPENAI_BASE_URL (or equivalent) at this proxy instead of the real API.

  Before:  OPENAI_BASE_URL=https://api.openai.com/v1
  After:   OPENAI_BASE_URL=http://kynara-proxy:8080/v1

Every request is:
  1. Inspected for tool calls (OpenAI function_call, Anthropic tool_use, generic)
  2. Checked against Kynara policy (via sidecar → central API → fail_open/closed)
  3. Forwarded to the real upstream if allowed, blocked with 403 if denied
  4. Audit-logged regardless of outcome

For LLM completion APIs (OpenAI /chat/completions, Anthropic /messages) the proxy
ALSO inspects the *response* and strips any tool_calls the model requested that
are policy-denied, injecting synthetic "permission_denied" tool results so the
conversation can continue gracefully.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

import audit
import inspector
import policy
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("kynara.proxy")

app = FastAPI(
    title="Kynara Proxy",
    description="Tier 0 transparent enforcement proxy — zero agent code changes required.",
    version="1.0.0",
)

# Single shared async HTTP client — reused across requests for connection pooling
_client: httpx.AsyncClient | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.upstream_url,
        timeout=settings.upstream_timeout,
        follow_redirects=True,
    )
    logger.info(
        "kynara-proxy started | upstream=%s sidecar=%s fail_open=%s port=%d",
        settings.upstream_url,
        settings.sidecar_url,
        settings.fail_open,
        settings.port,
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _client:
        await _client.aclose()


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/_kynara/health")
async def health() -> dict:
    return {"ok": True, "upstream": settings.upstream_url}


@app.get("/_kynara/config")
async def config_info() -> dict:
    """Show non-sensitive config for debugging."""
    return {
        "upstream_url": settings.upstream_url,
        "sidecar_url": settings.sidecar_url,
        "fail_open": settings.fail_open,
        "agent_id_header": settings.agent_id_header,
        "audit_log_path": settings.audit_log_path,
    }


# ── Main proxy route ──────────────────────────────────────────────────────

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(request: Request, path: str) -> Response:
    agent_id = (
        request.headers.get(settings.agent_id_header)
        or request.headers.get("x-agent-id")
        or "anonymous"
    )

    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    t0 = time.monotonic()

    # ── Step 1: Inspect the request for tool calls ────────────────────────
    result = inspector.inspect_request(raw_body, content_type, f"/{path}")

    if not result.has_tool_calls:
        # No tool calls in the request — pass through, but still log
        audit.log_passthrough(
            path=f"/{path}",
            method=request.method,
            agent_id=agent_id,
            reason="no_tool_calls_in_request",
        )
        upstream_resp = await _forward(request, path, raw_body)

        # For LLM completion endpoints, also inspect the *response* for tool calls
        if _is_completion_path(path):
            upstream_resp = await _enforce_response_tool_calls(
                upstream_resp, agent_id, path, request.method
            )

        return _to_response(upstream_resp)

    # ── Step 2: Check policy for each tool call ───────────────────────────
    denied: list[inspector.ToolCall] = []
    approved: list[inspector.ToolCall] = []

    for tc in result.tool_calls:
        dec = await policy.check(
            agent_id=agent_id,
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            context={"path": f"/{path}", "method": request.method},
        )
        audit.log_decision(
            agent_id=agent_id,
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            decision=dec,
            path=f"/{path}",
            method=request.method,
        )
        logger.info(
            "decision | agent=%s tool=%s effect=%s reason=%s latency=%.1fms",
            agent_id, tc.tool_name, dec.effect, dec.reason,
            (time.monotonic() - t0) * 1000,
        )

        if dec.effect == "deny":
            denied.append(tc)
        elif dec.effect == "require_approval":
            # Return 202 immediately — agent must poll the approval URL
            return JSONResponse(
                status_code=202,
                content={
                    "error": "approval_required",
                    "tool": tc.tool_name,
                    "approval_url": dec.approval_url,
                    "decision_id": dec.decision_id,
                    "message": (
                        f"Tool '{tc.tool_name}' requires human approval. "
                        f"Poll {dec.approval_url} for the decision."
                    ),
                },
            )
        else:
            approved.append(tc)

    # ── Step 3: Block if any tool was denied ──────────────────────────────
    if denied:
        tool_names = [tc.tool_name for tc in denied]
        logger.warning("blocked | agent=%s denied_tools=%s", agent_id, tool_names)
        return JSONResponse(
            status_code=403,
            content={
                "error": "permission_denied",
                "denied_tools": tool_names,
                "message": (
                    f"Kynara blocked {len(denied)} tool call(s): "
                    f"{', '.join(tool_names)}. "
                    "Check your agent's assigned role and policies."
                ),
            },
        )

    # ── Step 4: Forward the request upstream ─────────────────────────────
    upstream_resp = await _forward(request, path, raw_body)
    return _to_response(upstream_resp)


# ── Helpers ───────────────────────────────────────────────────────────────

async def _forward(
    request: Request, path: str, body: bytes
) -> httpx.Response:
    """Forward the original request to the upstream API."""
    # Strip hop-by-hop headers and the Kynara identity header
    skip = {
        "host", "content-length", "transfer-encoding",
        settings.agent_id_header.lower(), settings.org_id_header.lower(),
    }
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in skip
    }
    return await _client.request(
        method=request.method,
        url=f"/{path}",
        params=dict(request.query_params),
        headers=headers,
        content=body,
    )


async def _enforce_response_tool_calls(
    upstream_resp: httpx.Response,
    agent_id: str,
    path: str,
    method: str,
) -> httpx.Response:
    """
    Inspect an LLM response body for tool_calls the model wants to execute.
    Strip denied calls and inject synthetic permission_denied results so the
    agent's conversation can continue without breaking.

    Returns a (possibly modified) response.
    """
    content_type = upstream_resp.headers.get("content-type", "")
    result = inspector.inspect_response(upstream_resp.content, content_type)

    if not result.has_tool_calls or result.body is None:
        return upstream_resp

    body = result.body
    any_denied = False

    for tc in result.tool_calls:
        dec = await policy.check(
            agent_id=agent_id,
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            context={"path": f"/{path}", "method": method, "phase": "response"},
        )
        audit.log_decision(
            agent_id=agent_id,
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            decision=dec,
            path=f"/{path}",
            method=method,
        )

        if dec.effect == "deny":
            any_denied = True
            _rewrite_deny_in_response(body, tc, dec.reason)

    if not any_denied:
        return upstream_resp

    # Rebuild the response with the rewritten body
    new_body = json.dumps(body).encode()
    headers = dict(upstream_resp.headers)
    headers["content-length"] = str(len(new_body))
    return httpx.Response(
        status_code=upstream_resp.status_code,
        headers=headers,
        content=new_body,
    )


def _rewrite_deny_in_response(
    body: dict[str, Any], tc: inspector.ToolCall, reason: str
) -> None:
    """
    Mutate *body* in place:
    - OpenAI: remove the denied tool_call from choices[].message.tool_calls
    - Anthropic: replace the tool_use block with a text explanation
    """
    if tc.source == "openai":
        for choice in body.get("choices", []):
            msg = choice.get("message", {})
            msg["tool_calls"] = [
                t for t in msg.get("tool_calls", [])
                if t.get("function", {}).get("name") != tc.tool_name
            ]
            # If all tool calls stripped, flip finish_reason back to stop
            if not msg["tool_calls"]:
                choice["finish_reason"] = "stop"
                msg["content"] = (
                    f"[Kynara] The tool '{tc.tool_name}' is not permitted for this agent. "
                    f"Reason: {reason}"
                )

    elif tc.source == "anthropic":
        new_content = []
        for block in body.get("content", []):
            if (
                block.get("type") == "tool_use"
                and block.get("name") == tc.tool_name
            ):
                new_content.append({
                    "type": "text",
                    "text": (
                        f"[Kynara] Tool '{tc.tool_name}' was blocked. "
                        f"Reason: {reason}"
                    ),
                })
            else:
                new_content.append(block)
        body["content"] = new_content
        body["stop_reason"] = "end_turn"


def _is_completion_path(path: str) -> bool:
    return any(s in path for s in ("chat/completions", "messages", "completions"))


def _to_response(upstream: httpx.Response) -> Response:
    skip = {"transfer-encoding", "content-encoding"}
    headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in skip
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=headers,
    )


# ── Entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )
