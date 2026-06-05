"""
Unit tests for the wrapper's gateway control-plane client (gateway.py).

These stub out httpx, so NO live backend or MCP server is required:

    cd kynara-mcp-wrapper
    python tests/test_gateway.py

Exit code 0 = all passed.
"""
import asyncio
import importlib
import os
import sys
from pathlib import Path

# Make the wrapper package importable when run from tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ── Fake httpx client ────────────────────────────────────────────────────────

class _FakeResp:
    def __init__(self, data):
        self._d = data
    def raise_for_status(self):
        return None
    def json(self):
        return self._d


class FakeClient:
    """Records calls and returns canned MCP-gateway responses."""
    last_post = None

    def __init__(self, *a, **k):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, headers=None):
        assert headers and headers.get("Authorization", "").startswith("Bearer "), "missing bearer auth"
        if url.endswith("/config"):
            return _FakeResp({
                "id": "srv-1", "slug": "crm", "transport": "sse", "fail_mode": "closed",
                "tools": {
                    "contacts.read": {"scope": "mcp.crm.contacts.read",
                                      "effect_override": None, "risk_class": "low"},
                    "contacts.delete": {"scope": "mcp.crm.contacts.delete",
                                        "effect_override": "require_approval", "risk_class": "high"},
                },
            })
        if url.endswith("/allowed-tools"):
            assert params and params.get("subject_id"), "allowed-tools needs subject_id"
            return _FakeResp({"tools": [
                {"name": "contacts.read", "scope": "mcp.crm.contacts.read", "effect": "allow"},
            ]})
        return _FakeResp({})

    async def post(self, url, json=None, headers=None):
        FakeClient.last_post = {"url": url, "json": json}
        return _FakeResp({"synced": len(json["tools"]), "server_id": "srv-1"})


class FakeTool:
    """Mimics mcp.types.Tool just enough for sync_tools."""
    def __init__(self, name, description=None, input_schema=None):
        self.name = name
        self.description = description
        self.inputSchema = input_schema or {}


# ── Test harness ─────────────────────────────────────────────────────────────

PASSED = 0
FAILED = 0

def check(label, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ✓ {label}")
    else:
        FAILED += 1
        print(f"  ✗ {label}")


def load_gateway(enabled: bool):
    """Import gateway.py with env reflecting enabled/disabled, and stub httpx."""
    if enabled:
        os.environ["KYNARA_MCP_SERVER_ID"] = "srv-1"
        os.environ["KYNARA_API_KEY"] = "sk_test_123"
        os.environ["KYNARA_API_BASE_URL"] = "http://backend.test"
    else:
        os.environ.pop("KYNARA_MCP_SERVER_ID", None)
        os.environ.pop("KYNARA_API_KEY", None)
    import gateway
    importlib.reload(gateway)
    gateway.httpx.AsyncClient = FakeClient
    return gateway


async def run() -> None:
    print("MCP wrapper gateway — unit tests\n")

    # ── Enabled path ──────────────────────────────────────────────────────
    gw = load_gateway(enabled=True)
    check("gateway reports ENABLED when server id + key set", gw.ENABLED is True)

    cfg = await gw.get_config(force=True)
    check("config returns tool map", "contacts.read" in cfg.get("tools", {}))

    scope = await gw.scope_for_tool("contacts.read")
    check("scope_for_tool maps known tool", scope == "mcp.crm.contacts.read")

    missing = await gw.scope_for_tool("nope.unknown")
    check("scope_for_tool returns None for unknown tool", missing is None)

    ovr = await gw.effect_override_for_tool("contacts.delete")
    check("effect_override_for_tool reads admin override", ovr == "require_approval")
    check("effect_override_for_tool None when policy decides",
          await gw.effect_override_for_tool("contacts.read") is None)

    check("fail_open reflects per-server fail_mode (closed -> False)",
          await gw.fail_open() is False)

    allowed = await gw.allowed_tool_names("agent-uuid-1")
    check("allowed_tool_names returns least-privilege set",
          allowed == {"contacts.read"})

    anon = await gw.allowed_tool_names("anonymous")
    check("allowed_tool_names skips filtering for anonymous (returns None)", anon is None)

    await gw.sync_tools([
        FakeTool("contacts.read", "Read a contact", {"type": "object"}),
        FakeTool("contacts.delete", "Delete a contact"),
    ])
    posted = FakeClient.last_post
    check("sync_tools posts to /tools/sync (no colon in path)",
          posted and posted["url"].endswith("/tools/sync"))
    check("sync_tools sends both discovered tools",
          posted and len(posted["json"]["tools"]) == 2)
    check("sync_tools maps inputSchema -> input_schema",
          posted and posted["json"]["tools"][0].get("input_schema") == {"type": "object"})

    # ── Disabled path (graceful degradation) ──────────────────────────────
    gw = load_gateway(enabled=False)
    check("gateway reports not ENABLED without config", gw.ENABLED is False)
    check("get_config returns empty when disabled", await gw.get_config(force=True) == {})
    check("scope_for_tool returns None when disabled",
          await gw.scope_for_tool("contacts.read") is None)
    check("allowed_tool_names returns None when disabled (no filtering)",
          await gw.allowed_tool_names("agent-uuid-1") is None)
    check("fail_open returns None when disabled (use wrapper default)",
          await gw.fail_open() is None)

    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    asyncio.run(run())
