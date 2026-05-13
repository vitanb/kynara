"""Kynara MCP server — exposes Kynara tools over Streamable HTTP (MCP 2025 spec).

Mount at /mcp/v1 in main.py.  Authentication uses the same Bearer token /
API-key mechanism as the REST API.

Endpoints
---------
GET|POST|DELETE  /mcp/v1   — single Streamable HTTP endpoint (MCP 2025)

Tools exposed
-------------
kynara_list_agents            list all agents in the org
kynara_get_agent              get one agent by id or slug
kynara_create_agent           register a new agent
kynara_kill_agent             disable / kill an agent
kynara_get_agent_access_summary  full permission matrix for an agent
kynara_check_permission       evaluate a policy decision (dry-run)
kynara_list_approvals         list approval requests (filterable by status)
kynara_approve_request        approve a pending approval
kynara_reject_request         reject a pending approval
kynara_list_roles             list all roles
kynara_create_role            create a new role with scopes
kynara_update_role            update a role's display name / scopes
kynara_delete_role            delete a role
kynara_assign_role            assign a role to an agent
kynara_list_audit_logs        query the audit log
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from mcp import types as mct
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import (
    Agent, AgentAssignment, ApprovalRequest, AuditEvent,
    Role, RolePermission,
)

# ── router (mounted at /mcp/v1 in main.py) ────────────────────────────────────
router = APIRouter(prefix="/mcp/v1", tags=["mcp"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _db():
    async with SessionLocal() as s:
        yield s


def _ok(data: Any) -> list[mct.TextContent]:
    return [mct.TextContent(type="text", text=json.dumps(data, default=str))]


def _err(msg: str) -> list[mct.TextContent]:
    return [mct.TextContent(type="text", text=json.dumps({"error": msg}))]


# ─────────────────────────────────────────────────────────────────────────────
# Build the MCP Server (stateless — recreated per SSE session)
# ─────────────────────────────────────────────────────────────────────────────

def _build_server(principal: Principal) -> Server:
    srv = Server("kynara")
    org_id = uuid.UUID(principal.org_id)

    # ── Tool registry ──────────────────────────────────────────────────────

    @srv.list_tools()
    async def list_tools() -> list[mct.Tool]:
        RO  = mct.ToolAnnotations(readOnlyHint=True,  destructiveHint=False)
        MUT = mct.ToolAnnotations(readOnlyHint=False, destructiveHint=False)
        DEL = mct.ToolAnnotations(readOnlyHint=False, destructiveHint=True)
        return [
            mct.Tool(
                name="kynara_list_agents",
                description="List all AI agents registered in this organisation.",
                inputSchema={"type": "object", "properties": {}, "required": []},
                annotations=RO,
            ),
            mct.Tool(
                name="kynara_get_agent",
                description="Get details for a single agent by id or slug.",
                inputSchema={
                    "type": "object",
                    "properties": {"agent_id": {"type": "string", "description": "Agent UUID or slug"}},
                    "required": ["agent_id"],
                },
                annotations=RO,
            ),
            mct.Tool(
                name="kynara_create_agent",
                description="Register a new AI agent in the organisation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "display_name": {"type": "string"},
                        "description": {"type": "string"},
                        "mode": {"type": "string", "enum": ["autonomous", "human_supervised", "locked"], "default": "human_supervised"},
                    },
                    "required": ["slug", "display_name"],
                },
                annotations=MUT,
            ),
            mct.Tool(
                name="kynara_kill_agent",
                description="Immediately disable an agent, revoking all active sessions.",
                inputSchema={
                    "type": "object",
                    "properties": {"agent_id": {"type": "string"}},
                    "required": ["agent_id"],
                },
                annotations=DEL,
            ),
            mct.Tool(
                name="kynara_get_agent_access_summary",
                description="Return the full permission matrix for an agent -- all allowed and denied scopes across every policy.",
                inputSchema={
                    "type": "object",
                    "properties": {"agent_id": {"type": "string"}},
                    "required": ["agent_id"],
                },
                annotations=RO,
            ),
            mct.Tool(
                name="kynara_check_permission",
                description=(
                    "Evaluate whether an agent is permitted to perform a tool/action. "
                    "Returns decision: allow | deny | require_approval, plus the governing policy."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id":  {"type": "string", "description": "Agent UUID or slug"},
                        "tool":      {"type": "string", "description": "Tool / action name, e.g. read_file"},
                        "resource":  {"type": "string", "description": "Resource being accessed (optional)"},
                        "context":   {"type": "object", "description": "Extra key/value context (optional)"},
                    },
                    "required": ["agent_id", "tool"],
                },
                annotations=RO,
            ),
            mct.Tool(
                name="kynara_list_approvals",
                description="List approval requests. Filter by status: pending | approved | rejected.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["pending", "approved", "rejected"], "default": "pending"},
                        "limit":  {"type": "integer", "default": 25},
                    },
                    "required": [],
                },
                annotations=RO,
            ),
            mct.Tool(
                name="kynara_approve_request",
                description="Approve a pending approval request, allowing the agent to proceed.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "approval_id": {"type": "string"},
                        "note":        {"type": "string"},
                    },
                    "required": ["approval_id"],
                },
                annotations=MUT,
            ),
            mct.Tool(
                name="kynara_reject_request",
                description="Reject a pending approval request.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "approval_id": {"type": "string"},
                        "reason":      {"type": "string"},
                    },
                    "required": ["approval_id", "reason"],
                },
                annotations=MUT,
            ),
            mct.Tool(
                name="kynara_list_roles",
                description="List all roles defined in the organisation.",
                inputSchema={"type": "object", "properties": {}, "required": []},
                annotations=RO,
            ),
            mct.Tool(
                name="kynara_create_role",
                description="Create a new role with a set of allowed scopes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "slug":         {"type": "string"},
                        "display_name": {"type": "string"},
                        "description":  {"type": "string"},
                        "scopes":       {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["slug", "display_name"],
                },
                annotations=MUT,
            ),
            mct.Tool(
                name="kynara_update_role",
                description="Update a role's display name, description, or scopes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "role_id":      {"type": "string"},
                        "display_name": {"type": "string"},
                        "description":  {"type": "string"},
                        "scopes":       {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["role_id"],
                },
                annotations=MUT,
            ),
            mct.Tool(
                name="kynara_delete_role",
                description="Delete a role. Fails if agents are currently assigned to it.",
                inputSchema={
                    "type": "object",
                    "properties": {"role_id": {"type": "string"}},
                    "required": ["role_id"],
                },
                annotations=DEL,
            ),
            mct.Tool(
                name="kynara_assign_role",
                description="Assign a role to an agent.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "role_id":  {"type": "string"},
                    },
                    "required": ["agent_id", "role_id"],
                },
                annotations=MUT,
            ),
            mct.Tool(
                name="kynara_list_audit_logs",
                description="Query the audit log. Filter by agent, outcome, or time range.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "outcome":  {"type": "string", "enum": ["allow", "deny", "require_approval"]},
                        "since":    {"type": "string", "description": "ISO-8601 timestamp"},
                        "limit":    {"type": "integer", "default": 50},
                    },
                    "required": [],
                },
                annotations=RO,
            ),
        ]

    # ── Tool dispatch ──────────────────────────────────────────────────────

    @srv.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[mct.TextContent]:
        async with SessionLocal() as db:
            try:
                return await _dispatch(name, arguments, db, org_id, principal)
            except HTTPException as e:
                return _err(e.detail)
            except Exception as e:
                return _err(str(e))

    return srv


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────

async def _resolve_agent(agent_id: str, org_id: uuid.UUID, db: AsyncSession) -> Agent:
    """Resolve agent by UUID or slug."""
    try:
        uid = uuid.UUID(agent_id)
        agent = await db.scalar(
            select(Agent).where(Agent.id == uid, Agent.organization_id == org_id)
        )
    except ValueError:
        agent = await db.scalar(
            select(Agent).where(Agent.slug == agent_id, Agent.organization_id == org_id)
        )
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return agent


async def _dispatch(
    name: str,
    args: dict,
    db: AsyncSession,
    org_id: uuid.UUID,
    principal: Principal,
) -> list[mct.TextContent]:

    # ── kynara_list_agents ──────────────────────────────────────────────────
    if name == "kynara_list_agents":
        rows = (await db.scalars(
            select(Agent)
            .where(Agent.organization_id == org_id)
            .order_by(Agent.created_at.desc())
        )).all()
        return _ok([{
            "id": str(r.id), "slug": r.slug, "display_name": r.display_name,
            "mode": r.mode, "is_active": r.is_active,
            "last_action_at": r.last_action_at,
        } for r in rows])

    # ── kynara_get_agent ───────────────────────────────────────────────────
    if name == "kynara_get_agent":
        a = await _resolve_agent(args["agent_id"], org_id, db)
        return _ok({
            "id": str(a.id), "slug": a.slug, "display_name": a.display_name,
            "description": a.description, "mode": a.mode,
            "model": a.model, "is_active": a.is_active,
            "daily_action_budget": a.daily_action_budget,
            "last_action_at": a.last_action_at,
            "created_at": a.created_at,
        })

    # ── kynara_create_agent ────────────────────────────────────────────────
    if name == "kynara_create_agent":
        agent = Agent(
            organization_id=org_id,
            slug=args["slug"],
            display_name=args["display_name"],
            description=args.get("description"),
            mode=args.get("mode", "human_supervised"),
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return _ok({"id": str(agent.id), "slug": agent.slug, "created": True})

    # ── kynara_kill_agent ──────────────────────────────────────────────────
    if name == "kynara_kill_agent":
        a = await _resolve_agent(args["agent_id"], org_id, db)
        a.is_active = False
        await db.commit()
        return _ok({"agent_id": str(a.id), "slug": a.slug, "killed": True})

    # ── kynara_get_agent_access_summary ────────────────────────────────────
    if name == "kynara_get_agent_access_summary":
        a = await _resolve_agent(args["agent_id"], org_id, db)
        # Collect all scopes from active role assignments
        assignments = (await db.scalars(
            select(AgentAssignment).where(
                AgentAssignment.agent_id == a.id,
                AgentAssignment.is_active.is_(True),
            )
        )).all()
        scopes: list[str] = []
        roles_info = []
        for asgn in assignments:
            role = await db.get(Role, asgn.role_id)
            if not role:
                continue
            perms = (await db.scalars(
                select(RolePermission).where(RolePermission.role_id == role.id)
            )).all()
            role_scopes = [p.scope for p in perms]
            scopes.extend(role_scopes)
            roles_info.append({"role": role.display_name, "scopes": role_scopes})
        return _ok({
            "agent_id": str(a.id),
            "slug": a.slug,
            "is_active": a.is_active,
            "mode": a.mode,
            "roles": roles_info,
            "all_scopes": sorted(set(scopes)),
        })

    # ── kynara_check_permission ────────────────────────────────────────────
    if name == "kynara_check_permission":
        from app.policy.service import evaluate
        a = await _resolve_agent(args["agent_id"], org_id, db)
        result = await evaluate(
            db=db,
            org_id=org_id,
            agent=a,
            tool=args["tool"],
            resource=args.get("resource"),
            context=args.get("context") or {},
        )
        return _ok({
            "agent_id": str(a.id),
            "slug": a.slug,
            "tool": args["tool"],
            "resource": args.get("resource"),
            "decision": result.decision,
            "policy_id": str(result.policy_id) if result.policy_id else None,
            "policy_name": result.policy_name,
            "reason": result.reason,
        })

    # ── kynara_list_approvals ──────────────────────────────────────────────
    if name == "kynara_list_approvals":
        status_filter = args.get("status", "pending")
        limit = min(int(args.get("limit", 25)), 100)
        rows = (await db.scalars(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.organization_id == org_id,
                ApprovalRequest.status == status_filter,
            )
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
        )).all()
        return _ok([{
            "id": str(r.id),
            "status": r.status,
            "action": r.action,
            "subject_id": str(r.subject_id),
            "resource_type": r.resource_type,
            "resource_id": str(r.resource_id) if r.resource_id else None,
            "created_at": r.created_at,
            "expires_at": r.expires_at,
        } for r in rows])

    # ── kynara_approve_request ─────────────────────────────────────────────
    if name == "kynara_approve_request":
        from datetime import datetime, timezone
        req = await db.get(ApprovalRequest, uuid.UUID(args["approval_id"]))
        if not req or str(req.organization_id) != str(org_id):
            return _err("Approval request not found")
        if req.status != "pending":
            return _err(f"Request is already {req.status}")
        req.status = "approved"
        req.reviewed_by_user_id = uuid.UUID(principal.user_id) if principal.user_id else None
        req.reviewed_at = datetime.now(timezone.utc)
        req.review_note = args.get("note")
        await db.commit()
        return _ok({"approval_id": args["approval_id"], "result": "approved"})

    # ── kynara_reject_request ──────────────────────────────────────────────
    if name == "kynara_reject_request":
        from datetime import datetime, timezone
        req = await db.get(ApprovalRequest, uuid.UUID(args["approval_id"]))
        if not req or str(req.organization_id) != str(org_id):
            return _err("Approval request not found")
        if req.status != "pending":
            return _err(f"Request is already {req.status}")
        req.status = "rejected"
        req.reviewed_by_user_id = uuid.UUID(principal.user_id) if principal.user_id else None
        req.reviewed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        req.review_note = args.get("reason")
        await db.commit()
        return _ok({"approval_id": args["approval_id"], "result": "rejected"})

    # ── kynara_list_roles ──────────────────────────────────────────────────
    if name == "kynara_list_roles":
        roles = (await db.scalars(
            select(Role).where(Role.organization_id == org_id).order_by(Role.created_at)
        )).all()
        result = []
        for r in roles:
            perms = (await db.scalars(
                select(RolePermission).where(RolePermission.role_id == r.id)
            )).all()
            result.append({
                "id": str(r.id), "slug": r.slug,
                "display_name": r.display_name, "description": r.description,
                "scopes": [p.scope for p in perms], "is_system": r.is_system,
            })
        return _ok(result)

    # ── kynara_create_role ─────────────────────────────────────────────────
    if name == "kynara_create_role":
        role = Role(
            organization_id=org_id,
            slug=args["slug"],
            display_name=args["display_name"],
            description=args.get("description"),
        )
        db.add(role)
        await db.flush()
        for scope in args.get("scopes", []):
            db.add(RolePermission(role_id=role.id, scope=scope))
        await db.commit()
        return _ok({"id": str(role.id), "slug": role.slug, "created": True})

    # ── kynara_update_role ─────────────────────────────────────────────────
    if name == "kynara_update_role":
        role = await db.get(Role, uuid.UUID(args["role_id"]))
        if not role or str(role.organization_id) != str(org_id):
            return _err("Role not found")
        if "display_name" in args:
            role.display_name = args["display_name"]
        if "description" in args:
            role.description = args["description"]
        if "scopes" in args:
            existing = (await db.scalars(
                select(RolePermission).where(RolePermission.role_id == role.id)
            )).all()
            for p in existing:
                await db.delete(p)
            for scope in args["scopes"]:
                db.add(RolePermission(role_id=role.id, scope=scope))
        await db.commit()
        return _ok({"id": str(role.id), "updated": True})

    # ── kynara_delete_role ─────────────────────────────────────────────────
    if name == "kynara_delete_role":
        role = await db.get(Role, uuid.UUID(args["role_id"]))
        if not role or str(role.organization_id) != str(org_id):
            return _err("Role not found")
        # Check no active assignments
        count = await db.scalar(
            select(AgentAssignment)
            .where(AgentAssignment.role_id == role.id, AgentAssignment.is_active.is_(True))
        )
        if count:
            return _err("Cannot delete role — agents are currently assigned to it")
        await db.delete(role)
        await db.commit()
        return _ok({"id": args["role_id"], "deleted": True})

    # ── kynara_assign_role ─────────────────────────────────────────────────
    if name == "kynara_assign_role":
        a = await _resolve_agent(args["agent_id"], org_id, db)
        role = await db.get(Role, uuid.UUID(args["role_id"]))
        if not role or str(role.organization_id) != str(org_id):
            return _err("Role not found")
        asgn = AgentAssignment(
            agent_id=a.id,
            role_id=role.id,
            assigned_by_user_id=uuid.UUID(principal.user_id) if principal.user_id else None,
        )
        db.add(asgn)
        await db.commit()
        return _ok({"agent_id": str(a.id), "role_id": str(role.id), "assigned": True})

    # ── kynara_list_audit_logs ─────────────────────────────────────────────
    if name == "kynara_list_audit_logs":
        from datetime import datetime, timezone
        limit = min(int(args.get("limit", 50)), 200)
        q = select(AuditEvent).where(AuditEvent.organization_id == org_id)
        if args.get("outcome"):
            q = q.where(AuditEvent.outcome == args["outcome"])
        if args.get("since"):
            since_dt = datetime.fromisoformat(args["since"].replace("Z", "+00:00"))
            q = q.where(AuditEvent.ts >= since_dt)
        if args.get("agent_id"):
            q = q.where(AuditEvent.actor == f"agent:{args['agent_id']}")
        q = q.order_by(AuditEvent.ts.desc()).limit(limit)
        rows = (await db.scalars(q)).all()
        return _ok([{
            "id": str(r.id), "ts": r.ts, "event_type": r.event_type,
            "actor": r.actor, "outcome": r.outcome,
            "resource_type": r.resource_type,
            "resource_id": str(r.resource_id) if r.resource_id else None,
        } for r in rows])

    return _err(f"Unknown tool: {name}")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI route handlers
# ─────────────────────────────────────────────────────────────────────────────

from fastapi.responses import Response as _Response


async def _handle_mcp(request: Request, principal: Principal) -> _Response:
    """Shared Streamable HTTP handler.

    Captures the MCP response via a buffer send callable and returns it as a
    proper FastAPI Response.  This avoids the ASGI double-send problem that
    occurs when request._send is called inside handle_request and then FastAPI
    also tries to finalise the response.

    For stateless Streamable HTTP each POST is a single JSON round-trip so
    buffering the full body is fine.  GET (SSE) and DELETE are short too.
    """
    status_code: list[int] = []
    headers_raw: list[tuple[bytes, bytes]] = []
    body_chunks: list[bytes] = []

    async def _capture_send(message: dict) -> None:
        if message["type"] == "http.response.start":
            status_code.append(message.get("status", 200))
            headers_raw.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                body_chunks.append(chunk)

    srv = _build_server(principal)
    manager = StreamableHTTPSessionManager(app=srv, stateless=True)
    async with manager.run():
        await manager.handle_request(request.scope, request.receive, _capture_send)

    resp_headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in headers_raw}
    return _Response(
        content=b"".join(body_chunks),
        status_code=status_code[0] if status_code else 200,
        headers=resp_headers,
    )


@router.api_route("", methods=["GET", "POST", "DELETE"])
async def mcp_endpoint(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> _Response:
    """Streamable HTTP endpoint -- MCP 2025 spec (GET/POST/DELETE)."""
    return await _handle_mcp(request, principal)


@router.api_route("/sse", methods=["GET", "POST", "DELETE"])
async def mcp_endpoint_sse(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> _Response:
    """Legacy /sse path alias -- same Streamable HTTP handler."""
    return await _handle_mcp(request, principal)
