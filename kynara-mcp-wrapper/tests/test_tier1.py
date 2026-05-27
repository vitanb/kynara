"""
Tier 1 Test — kynara-mcp-wrapper policy enforcement.

Tests that the wrapper correctly:
  1. Exposes the same tools as the upstream MCP server (transparent)
  2. ALLOWS calls to permitted tools and returns real results
  3. BLOCKS calls to denied tools with a clear error message

Prerequisites (run these first in separate terminals):
  Terminal 1:  python tests/mock_sidecar.py
               # Mock policy engine on port 7070

  Terminal 2:  python tests/demo_mcp_server.py
               # Upstream MCP server on port 8000

  Terminal 3:  KYNARA_UPSTREAM_MCP_URL=http://localhost:8000/sse \\
               KYNARA_SIDECAR_URL=http://localhost:7070 \\
               KYNARA_FAIL_OPEN=false \\
               KYNARA_MCP_WRAPPER_PORT=9090 \\
               python main.py
               # Kynara MCP wrapper on port 9090

Then run this file:
  python tests/test_tier1.py
"""
import asyncio
import sys
import textwrap

from mcp import ClientSession
from mcp.client.sse import sse_client

WRAPPER_URL = "http://localhost:9090/sse"
AGENT_ID    = "test-agent-tier1"


def hr(title=""):
    width = 60
    if title:
        print(f"\n{'─'*4} {title} {'─'*(width - len(title) - 6)}")
    else:
        print("─" * width)


async def run_tests():
    print(textwrap.dedent(f"""
    ╔══════════════════════════════════════════╗
    ║   Kynara Tier 1 — Integration Test       ║
    ║   Wrapper : {WRAPPER_URL:<30}║
    ║   Agent   : {AGENT_ID:<30}║
    ╚══════════════════════════════════════════╝
    """))

    results = {}

    async with sse_client(
        url=WRAPPER_URL,
        headers={"x-kynara-agent": AGENT_ID},
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── Test 1: List tools ────────────────────────────────────────
            hr("TEST 1 — List tools (same as upstream)")
            tool_list = await session.list_tools()
            names = [t.name for t in tool_list.tools]
            print(f"  Tools visible to agent: {names}")
            expected = {"get_weather", "read_document", "send_email", "delete_file"}
            ok = expected.issubset(set(names))
            print(f"  {'✅' if ok else '❌'} All upstream tools re-exposed by wrapper")
            results["List tools transparent"] = ok

            # ── Test 2: Allowed tool — get_weather ────────────────────────
            hr("TEST 2 — Allowed tool: get_weather('London')")
            try:
                result = await session.call_tool("get_weather", {"city": "London"})
                text = result.content[0].text if result.content else ""
                ok = "°C" in text and not result.isError
                print(f"  Result : {text}")
                print(f"  {'✅' if ok else '❌'} Tool executed and result returned")
                results["Allowed: get_weather"] = ok
            except Exception as e:
                print(f"  ❌ Unexpected error: {e}")
                results["Allowed: get_weather"] = False

            # ── Test 3: Allowed tool — read_document ──────────────────────
            hr("TEST 3 — Allowed tool: read_document('/reports/q1.pdf')")
            try:
                result = await session.call_tool("read_document", {"path": "/reports/q1.pdf"})
                text = result.content[0].text if result.content else ""
                ok = len(text) > 0 and not result.isError
                print(f"  Result : {text[:80]}…")
                print(f"  {'✅' if ok else '❌'} Tool executed and result returned")
                results["Allowed: read_document"] = ok
            except Exception as e:
                print(f"  ❌ Unexpected error: {e}")
                results["Allowed: read_document"] = False

            # ── Test 4: DENIED tool — send_email ─────────────────────────
            hr("TEST 4 — DENIED tool: send_email (policy blocks it)")
            try:
                result = await session.call_tool(
                    "send_email",
                    {"to": "ceo@acme.com", "subject": "Exfiltrated data", "body": "..."},
                )
                # If we get here, check if it's an error result
                ok = result.isError
                text = result.content[0].text if result.content else ""
                if ok:
                    print(f"  ✅ Blocked with error: {text[:120]}")
                else:
                    print(f"  ❌ Tool was NOT blocked (should have been denied)")
                results["Denied: send_email"] = ok
            except Exception as e:
                # MCP errors also surface as exceptions
                blocked = "kynara" in str(e).lower() or "permission" in str(e).lower() or "denied" in str(e).lower()
                print(f"  {'✅' if blocked else '❌'} Exception: {str(e)[:120]}")
                results["Denied: send_email"] = blocked

            # ── Test 5: DENIED tool — delete_file ────────────────────────
            hr("TEST 5 — DENIED tool: delete_file (policy blocks it)")
            try:
                result = await session.call_tool(
                    "delete_file",
                    {"path": "/critical/database.db"},
                )
                ok = result.isError
                text = result.content[0].text if result.content else ""
                if ok:
                    print(f"  ✅ Blocked with error: {text[:120]}")
                else:
                    print(f"  ❌ Tool was NOT blocked")
                results["Denied: delete_file"] = ok
            except Exception as e:
                blocked = "kynara" in str(e).lower() or "permission" in str(e).lower() or "denied" in str(e).lower()
                print(f"  {'✅' if blocked else '❌'} Exception: {str(e)[:120]}")
                results["Denied: delete_file"] = blocked

    # ── Results ───────────────────────────────────────────────────────────
    hr("RESULTS")
    passed = sum(results.values())
    total  = len(results)
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'}  {name}")
    print(f"\n  {passed}/{total} passed")
    print()
    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
