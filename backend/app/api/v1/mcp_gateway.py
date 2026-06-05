"""MCP authorization gateway — control plane for upstream MCP servers.

Admins register upstream MCP servers; the Kynara MCP wrapper fronts them and
enforces policy on every tool call. Each discovered tool is mapped to a Kynara
capability scope so the existing RBAC/ABAC engine governs, per call, which agents
may invoke which tools (least privilege).

Endpoints
─────────
Admin (owner/admin seat):
  GET    /mcp/servers                     list registered servers
  POST   /mcp/servers                     register a server
  GET    /mcp/servers/{id}                server + its tools
  PATCH  /mcp/servers/{id}                update server config
  DELETE /mcp/servers/{id}                remove a server (+ its tools)
  PATCH  /mcp/tools/{tool_id}             edit a tool's scope/risk/effect/enabled

Wrapper (any authenticated principal in the org — typically an API key):
  POST   /mcp/servers/{id}/tools:sync     upsert discovered tools (auto-mapped)
  GET    /mcp/servers/{id}/config         server config + tool→scope map
  GET    /mcp/servers/{id}/allowed-tools  least-privilege tool list for a subject
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal, require_seat
from app.db.session import SessionLocal
from app.models.mcp_server import McpServer, McpTool
from app.policy.service import decide

router = APIRouter(prefix="/mcp", tags=["mcp-gateway"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:64] or "server"


def _auto_scope(prefix: str, tool_name: str) -> str:
    norm = re.sub(r"[^a-z0-9.]+", "_", tool_name.lower()).strip("_.")
    prefix = (prefix or "mcp").rstrip(".")
    return f"{prefix}.{norm}" if norm else prefix


# ── Schemas ─────────────────────────────────────────────────────────────────

class McpServerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    description: str | None = None
    transport: str = Field(default="sse", pattern=r"^(sse|http|stdio)$")
    url: str | None = None
    stdio_cmd: str | None = None
    upstream_headers: dict = Field(default_factory=dict)
    scope_prefix: str = Field(default="mcp", max_length=128)
    fail_mode: str = Field(default="closed", pattern=r"^(open|closed)$")
    require_approval_default: bool = False
    is_enabled: bool = True


class McpServerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    transport: str | None = Field(default=None, pattern=r"^(sse|http|stdio)$")
    url: str | None = None
    stdio_cmd: str | None = None
    upstream_headers: dict | None = None
    scope_prefix: str | None = None
    fail_mode: str | None = Field(default=None, pattern=r"^(open|closed)$")
    require_approval_default: bool | None = None
    is_enabled: bool | None = None


class McpToolOut(BaseModel):
    id: str
    name: str
    description: str | None
    scope: str
    risk_class: str
    effect_override: str | None
    is_enabled: bool


class McpServerOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    transport: str
    url: str | None
    stdio_cmd: str | None
    scope_prefix: str
    fail_mode: str
    require_approval_default: bool
    is_enabled: bool
    last_synced_at: str | None
    tool_count: int


class McpToolUpdate(BaseModel):
    scope: str | None = None
    risk_class: str | None = Field(default=None, pattern=r"^(low|medium|high|critical)$")
    effect_override: str | None = None  # "deny" | "require_approval" | "" (clear)
    is_enabled: bool | None = None


class ToolSyncItem(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict = Field(default_factory=dict)


class ToolSyncIn(BaseModel):
    tools: list[ToolSyncItem]


# ── Serializers ──────────────────────────────────────────────────────────────

def _server_out(s: McpServer) -> McpServerOut:
    return McpServerOut(
        id=str(s.id), name=s.name, slug=s.slug, description=s.description,
        transport=s.transport, url=s.url, stdio_cmd=s.stdio_cmd,
        scope_prefix=s.scope_prefix, fail_mode=s.fail_mode,
        require_approval_default=s.require_approval_default, is_enabled=s.is_enabled,
        last_synced_at=s.last_synced_at, tool_count=s.tool_count,
    )


def _tool_out(t: McpTool) -> McpToolOut:
    return McpToolOut(
        id=str(t.id), name=t.name, description=t.description, scope=t.scope,
        risk_class=t.risk_class, effect_override=t.effect_override, is_enabled=t.is_enabled,
    )


async def _get_owned_server(session: AsyncSession, org_id: str, server_id: str) -> McpServer:
    try:
        sid = uuid.UUID(server_id)
    except ValueError:
        raise HTTPException(400, "Invalid server id")
    srv = await session.get(McpServer, sid)
    if not srv or srv.organization_id != uuid.UUID(org_id):
        raise HTTPException(404, "MCP server not found")
    return srv


# ── Admin: servers ───────────────────────────────────────────────────────────

@router.get("/servers", response_model=list[McpServerOut])
async def list_servers(
    principal: Principal = Depends(require_seat("owner", "admin", "developer", "auditor")),
    session: AsyncSession = Depends(_session),
):
    rows = (await session.scalars(
        select(McpServer).where(McpServer.organization_id == uuid.UUID(principal.org_id))
        .order_by(McpServer.created_at.desc())
    )).all()
    return [_server_out(s) for s in rows]


@router.post("/servers", response_model=McpServerOut, status_code=201)
async def create_server(
    body: McpServerIn, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    org = uuid.UUID(principal.org_id)
    slug = _slugify(body.slug or body.name)
    # Ensure slug uniqueness within the org.
    exists = await session.scalar(
        select(McpServer).where(McpServer.organization_id == org, McpServer.slug == slug)
    )
    if exists:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    if body.transport in ("sse", "http") and not body.url:
        raise HTTPException(400, "url is required for sse/http transports")
    if body.transport == "stdio" and not body.stdio_cmd:
        raise HTTPException(400, "stdio_cmd is required for stdio transport")

    srv = McpServer(
        organization_id=org, name=body.name, slug=slug, description=body.description,
        transport=body.transport, url=body.url, stdio_cmd=body.stdio_cmd,
        upstream_headers=body.upstream_headers or {}, scope_prefix=body.scope_prefix or "mcp",
        fail_mode=body.fail_mode, require_approval_default=body.require_approval_default,
        is_enabled=body.is_enabled,
        created_by_user_id=uuid.UUID(principal.user_id) if principal.user_id else None,
    )
    session.add(srv)
    await session.flush()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="mcp_server.created", resource_type="mcp_server", resource_id=str(srv.id),
        payload={"name": srv.name, "slug": srv.slug, "transport": srv.transport},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return _server_out(srv)


@router.get("/servers/{server_id}")
async def get_server(
    server_id: str,
    principal: Principal = Depends(require_seat("owner", "admin", "developer", "auditor")),
    session: AsyncSession = Depends(_session),
):
    srv = await _get_owned_server(session, principal.org_id, server_id)
    tools = (await session.scalars(
        select(McpTool).where(McpTool.server_id == srv.id).order_by(McpTool.name)
    )).all()
    return {"server": _server_out(srv).model_dump(), "tools": [_tool_out(t).model_dump() for t in tools]}


@router.patch("/servers/{server_id}", response_model=McpServerOut)
async def update_server(
    server_id: str, body: McpServerUpdate, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    srv = await _get_owned_server(session, principal.org_id, server_id)
    patch = body.model_dump(exclude_unset=True)
    for k, v in patch.items():
        setattr(srv, k, v)
    await session.flush()
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="mcp_server.updated", resource_type="mcp_server", resource_id=str(srv.id),
        payload={"changed": list(patch.keys())},
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return _server_out(srv)


@router.delete("/servers/{server_id}", status_code=204)
async def delete_server(
    server_id: str, request: Request,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    srv = await _get_owned_server(session, principal.org_id, server_id)
    await record_admin(
        session, org_id=principal.org_id,
        actor=f"user:{principal.user_id}" if principal.user_id else "system",
        event_type="mcp_server.deleted", resource_type="mcp_server", resource_id=str(srv.id),
        payload={"name": srv.name}, ip_address=request.client.host if request.client else None,
    )
    await session.delete(srv)
    await session.commit()
    return None


# ── Admin: tools ─────────────────────────────────────────────────────────────

@router.patch("/tools/{tool_id}", response_model=McpToolOut)
async def update_tool(
    tool_id: str, body: McpToolUpdate,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    try:
        tid = uuid.UUID(tool_id)
    except ValueError:
        raise HTTPException(400, "Invalid tool id")
    tool = await session.get(McpTool, tid)
    if not tool or tool.organization_id != uuid.UUID(principal.org_id):
        raise HTTPException(404, "Tool not found")
    patch = body.model_dump(exclude_unset=True)
    if "effect_override" in patch and patch["effect_override"] in ("", None):
        patch["effect_override"] = None
    elif patch.get("effect_override") not in (None, "deny", "require_approval"):
        raise HTTPException(400, "effect_override must be 'deny', 'require_approval', or empty")
    for k, v in patch.items():
        setattr(tool, k, v)
    await session.commit()
    return _tool_out(tool)


# ── Wrapper: tool discovery sync ─────────────────────────────────────────────

@router.post("/servers/{server_id}/tools/sync")
async def sync_tools(
    server_id: str, body: ToolSyncIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    srv = await _get_owned_server(session, principal.org_id, server_id)
    existing = {
        t.name: t for t in (await session.scalars(
            select(McpTool).where(McpTool.server_id == srv.id)
        )).all()
    }
    seen: set[str] = set()
    for item in body.tools:
        seen.add(item.name)
        t = existing.get(item.name)
        if t:
            # Preserve admin-edited scope/risk/effect; only refresh metadata.
            t.description = item.description
            t.input_schema = item.input_schema or {}
        else:
            t = McpTool(
                organization_id=srv.organization_id, server_id=srv.id, name=item.name,
                description=item.description, input_schema=item.input_schema or {},
                scope=_auto_scope(srv.scope_prefix, item.name), risk_class="low",
                effect_override="require_approval" if srv.require_approval_default else None,
                is_enabled=True,
            )
            session.add(t)
    # Tools no longer advertised upstream are disabled (not deleted, to keep audit).
    for name, t in existing.items():
        if name not in seen:
            t.is_enabled = False
    srv.last_synced_at = datetime.now(timezone.utc).isoformat()
    srv.tool_count = len(seen)
    await session.commit()
    return {"synced": len(seen), "server_id": str(srv.id)}


# ── Wrapper: config + least-privilege list ───────────────────────────────────

@router.get("/servers/{server_id}/config")
async def server_config(
    server_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    srv = await _get_owned_server(session, principal.org_id, server_id)
    tools = (await session.scalars(
        select(McpTool).where(McpTool.server_id == srv.id, McpTool.is_enabled.is_(True))
    )).all()
    # upstream_headers may carry the upstream's auth token — only expose to the
    # wrapper (API key) or org admins, never to read-only/auditor sessions.
    may_see_secrets = principal.auth_method == "api_key" or principal.seat_role in ("owner", "admin")
    return {
        "id": str(srv.id), "slug": srv.slug, "transport": srv.transport,
        "url": srv.url, "stdio_cmd": srv.stdio_cmd,
        "upstream_headers": srv.upstream_headers if may_see_secrets else {},
        "fail_mode": srv.fail_mode, "is_enabled": srv.is_enabled,
        "tools": {
            t.name: {"scope": t.scope, "effect_override": t.effect_override,
                     "risk_class": t.risk_class}
            for t in tools
        },
    }


@router.get("/servers/{server_id}/allowed-tools")
async def allowed_tools(
    server_id: str,
    subject_type: str = "agent",
    subject_id: str = "",
    on_behalf_of_user_id: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    """Return only the tools a subject may see/invoke (allow or require_approval).

    Denied tools are omitted entirely — least-privilege discovery.
    """
    srv = await _get_owned_server(session, principal.org_id, server_id)
    if not subject_id:
        raise HTTPException(400, "subject_id is required")
    tools = (await session.scalars(
        select(McpTool).where(McpTool.server_id == srv.id, McpTool.is_enabled.is_(True))
    )).all()
    out: list[dict] = []
    for t in tools:
        if t.effect_override == "deny":
            continue
        decision = await decide(
            session, org_id=principal.org_id, subject_type=subject_type,
            subject_id=subject_id, on_behalf_of_user_id=on_behalf_of_user_id,
            action=t.scope, resource={"type": "mcp_tool", "id": t.name, "attrs": {}},
            context={},
        )
        effect = t.effect_override or decision.effect
        if effect == "deny":
            continue
        out.append({"name": t.name, "scope": t.scope, "effect": effect,
                    "risk_class": t.risk_class})
    return {"server_id": str(srv.id), "tools": out}
