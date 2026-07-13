# Kynara MCP Gateway — authorization & policy enforcement for MCP servers

**Put Kynara in front of any [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server so every tool call is authorized, per agent, before it runs.** The Kynara MCP Gateway is a drop-in proxy that adds RBAC + ABAC policy enforcement, human-in-the-loop approvals, least-privilege tool discovery, and a tamper-evident audit log to MCP servers your AI agents already use — with **zero agent-side code changes**.

> Keywords: MCP gateway, MCP authorization, MCP server security, AI agent permissions, least-privilege MCP, MCP policy enforcement, MCP access control, AI agent governance.

---

## Why

MCP makes it trivial for an AI agent to call tools — read a database, send email, deploy code, issue a refund. But MCP has no built-in answer to *which agent is allowed to call which tool, on whose behalf, under what conditions.* The Kynara MCP Gateway closes that gap.

- **Per-call authorization** — every `tools/call` is checked against your Kynara policies and returns `allow`, `deny`, or `require_approval`.
- **Least-privilege discovery** — agents only see the tools they're permitted to use; denied tools are never even advertised.
- **Human-in-the-loop** — high-risk tools can require human approval before they run.
- **Tamper-evident audit** — every decision is recorded in Kynara's SHA-256 hash-chained log.
- **Drop-in** — agents swap one URL; no SDK changes required.

## How it works

```
AI agent  ──►  Kynara MCP Gateway  ──►  your upstream MCP server
                     │
                     └─►  Kynara decision engine (allow / deny / require_approval)
```

On startup the gateway discovers the upstream server's tools and registers them with Kynara, where each tool is mapped to a capability scope (e.g. `mcp.crm.contacts.read`). On every call it resolves the tool's scope and asks the decision engine; on every `list_tools` it filters to the agent's allowed tools.

## Quick start

```bash
pip install -r requirements.txt

# Front an upstream MCP server, centrally governed by Kynara:
KYNARA_UPSTREAM_MCP_URL=https://your-mcp-server.example.com/sse \
KYNARA_API_BASE_URL=https://kynaraai.com \
KYNARA_API_KEY=sk_live_xxx \
KYNARA_MCP_SERVER_ID=<server id from the Kynara MCP Gateway page> \
KYNARA_MCP_WRAPPER_PORT=9090 \
python main.py
```

Then point your agent at the gateway instead of the upstream:

```jsonc
// before
{ "url": "https://your-mcp-server.example.com/sse" }
// after
{ "url": "http://kynara-mcp-gateway:9090/sse" }
```

## Configuration

| Variable | Description |
|----------|-------------|
| `KYNARA_UPSTREAM_MCP_URL` | Upstream MCP server (SSE). Use `KYNARA_UPSTREAM_STDIO_CMD` for stdio. |
| `KYNARA_API_BASE_URL` | Kynara API base URL. |
| `KYNARA_API_KEY` | Kynara API key (`sk_live_…`) used to fetch config and check decisions. |
| `KYNARA_MCP_SERVER_ID` | Registers this gateway with a server in Kynara → enables central tool→scope mapping and least-privilege filtering. |
| `KYNARA_SIDECAR_URL` | Optional local sidecar for sub-millisecond decisions. |
| `KYNARA_FAIL_OPEN` | Fallback when Kynara is unreachable (`false` = fail-closed, the default). Overridden by the per-server fail mode when the gateway is configured. |
| `KYNARA_MCP_WRAPPER_PORT` | Listen port (default `9090`). |

When `KYNARA_MCP_SERVER_ID` + `KYNARA_API_KEY` are set, the gateway pulls its tool→scope map and the connecting agent's allowed-tools list from Kynara; otherwise it falls back to a basic per-call policy check.

## Learn more

- Product: https://kynaraai.com
- Docs: https://kynaraai.com/docs  (see the **MCP Gateway** section)
- Sandbox: https://kynaraai.com/sandbox

---

*Kynara is a permission control plane for AI agents — RBAC + ABAC, human approvals, MCP enforcement, and a tamper-evident audit log. Source-available under BSL 1.1.*
