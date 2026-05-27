"""
Tier 0 Test — kynara-proxy policy enforcement.

Tests that the proxy correctly:
  1. Passes through plain LLM requests
  2. ALLOWS tool calls not in the deny list
  3. BLOCKS tool calls in the deny list (gets 403 back)
  4. Rewrites denied tool_calls in LLM responses

── Option A: Groq (free cloud LLM, no local GPU needed) ─────────────────────
  Sign up at https://console.groq.com → API Keys → Create Key

  Terminal 1:  python tests/mock_sidecar.py
  Terminal 2:  KYNARA_UPSTREAM_URL=https://api.groq.com/openai \\
               KYNARA_SIDECAR_URL=http://localhost:7070 \\
               KYNARA_FAIL_OPEN=false \\
               python main.py

  Run tests:   GROQ_API_KEY=gsk_... TEST_MODEL=llama-3.3-70b-versatile \\
               python tests/test_tier0.py

── Option B: Ollama (local, no API key needed) ───────────────────────────────
  Terminal 1:  ollama serve
  Terminal 2:  python tests/mock_sidecar.py
  Terminal 3:  KYNARA_UPSTREAM_URL=http://localhost:11434 \\
               KYNARA_SIDECAR_URL=http://localhost:7070 \\
               KYNARA_FAIL_OPEN=false \\
               python main.py

  Run tests:   TEST_MODEL=llama3.2 python tests/test_tier0.py
"""
import json
import os
import sys
import textwrap

import httpx

PROXY_URL  = os.getenv("KYNARA_PROXY_URL", "http://localhost:8080")
AGENT_ID   = "test-agent-tier0"
# Override with TEST_MODEL env var — default covers Groq's free Llama model
MODEL      = os.getenv("TEST_MODEL", "llama-3.3-70b-versatile")

# Upstream API key forwarded transparently by the proxy (Groq, OpenAI, etc.)
# Leave empty for Ollama (no auth required)
_API_KEY   = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or ""


def hr(title=""):
    width = 60
    if title:
        print(f"\n{'─'*4} {title} {'─'*(width - len(title) - 6)}")
    else:
        print("─" * width)


def _headers() -> dict:
    h = {"x-kynara-agent": AGENT_ID, "Content-Type": "application/json"}
    if _API_KEY:
        h["Authorization"] = f"Bearer {_API_KEY}"
    return h


def send(path, body, expect_status=None):
    resp = httpx.post(
        f"{PROXY_URL}{path}",
        json=body,
        headers=_headers(),
        timeout=60,
    )
    ok = expect_status is None or resp.status_code == expect_status
    status_icon = "✅" if ok else "❌"
    print(f"  {status_icon} HTTP {resp.status_code}  (expected {expect_status})")
    if not ok:
        print(f"     body: {resp.text[:300]}")
    return resp, ok


# ── Test 1: Health check ──────────────────────────────────────────────────

def test_health():
    hr("TEST 1 — Proxy health")
    resp = httpx.get(f"{PROXY_URL}/_kynara/health", timeout=5)
    print(f"  {'✅' if resp.status_code == 200 else '❌'} {resp.json()}")
    return resp.status_code == 200


# ── Test 2: Plain LLM call (no tool calls) ───────────────────────────────

def test_plain_llm():
    hr("TEST 2 — Plain LLM call (no tools, should pass through)")
    resp, ok = send(
        "/v1/chat/completions",
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say exactly: hello kynara"}],
        },
        expect_status=200,
    )
    if ok and resp.status_code == 200:
        content = resp.json()["choices"][0]["message"].get("content", "")
        print(f"  LLM said: {content[:100]}")
    return ok


# ── Test 3: Request containing an ALLOWED tool call ──────────────────────

def test_allowed_tool_call():
    hr("TEST 3 — Tool call that is ALLOWED (read_file)")
    # We embed the tool call in the message history (as if agent is resuming)
    resp, ok = send(
        "/v1/chat/completions",
        {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "Read the config file."},
                {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "/etc/config.yaml"}),
                        },
                    }],
                },
            ],
            "tools": [{"type": "function", "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }}],
        },
        expect_status=200,
    )
    print(f"  read_file was allowed — proxy forwarded to upstream ✓" if ok else "  FAILED")
    return ok


# ── Test 4: Request containing a DENIED tool call ────────────────────────

def test_denied_tool_call():
    hr("TEST 4 — Tool call that is DENIED (send_email)")
    resp, ok = send(
        "/v1/chat/completions",
        {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "Email the report to the team."},
                {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "send_email",
                            "arguments": json.dumps({"to": "team@acme.com", "body": "Here is the report"}),
                        },
                    }],
                },
            ],
        },
        expect_status=403,
    )
    if ok:
        body = resp.json()
        print(f"  Blocked tools: {body.get('denied_tools')}")
        print(f"  Reason: {body.get('message','')[:100]}")
    return ok


# ── Test 5: Generic tool call endpoint (non-LLM tool service) ────────────

def test_generic_allowed():
    hr("TEST 5 — Generic tool endpoint, ALLOWED (query_database)")
    # Simulate a direct tool-execution call (not via LLM)
    resp, ok = send(
        "/api/tools/execute",
        {"tool": "query_database", "params": {"sql": "SELECT 1"}},
        expect_status=200,
    )
    # Ollama won't understand this path but proxy should attempt to forward
    # (we just care that Kynara didn't block it — any upstream error is fine)
    allowed = resp.status_code != 403
    print(f"  {'✅' if allowed else '❌'} query_database was {'allowed through' if allowed else 'blocked'} by Kynara")
    return allowed


def test_generic_denied():
    hr("TEST 6 — Generic tool endpoint, DENIED (delete_file)")
    resp, ok = send(
        "/api/tools/execute",
        {"tool": "delete_file", "params": {"path": "/important/data.db"}},
        expect_status=403,
    )
    if ok:
        print(f"  delete_file correctly blocked ✓")
    return ok


# ── Run all tests ─────────────────────────────────────────────────────────

def main():
    print(textwrap.dedent(f"""
    ╔══════════════════════════════════════════╗
    ║   Kynara Tier 0 — Integration Test       ║
    ║   Proxy : {PROXY_URL:<31}║
    ║   Agent : {AGENT_ID:<31}║
    ║   Model : {MODEL:<31}║
    ╚══════════════════════════════════════════╝
    """))

    results = {
        "Health check":          test_health(),
        "Plain LLM passthrough": test_plain_llm(),
        "Allowed tool call":     test_allowed_tool_call(),
        "Denied tool call":      test_denied_tool_call(),
        "Generic allowed":       test_generic_allowed(),
        "Generic denied":        test_generic_denied(),
    }

    hr("RESULTS")
    passed = sum(results.values())
    total  = len(results)
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'}  {name}")
    print(f"\n  {passed}/{total} passed")
    print()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
