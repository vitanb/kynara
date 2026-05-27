# Kynara — Local Testing Guide

Test **Tier 0** (transparent HTTP proxy) and **Tier 1** (MCP server wrapper) on your laptop
using free AI services. No paid accounts, no cloud infrastructure required.

---

## What you're testing

| Tier | What it is | What you'll see |
|------|-----------|-----------------|
| **Tier 0** | Kynara sits in front of any LLM API. Zero code changes for the agent. | Dangerous tool calls (`send_email`, `delete_file`) blocked with HTTP 403. Safe ones pass through. |
| **Tier 1** | Kynara wraps an MCP server. Agents swap one URL. | MCP tool calls enforced — denied tools return a structured error; allowed tools return real results. |

---

## Prerequisites

Install these once. Everything else is handled by the steps below.

### 1 — Python 3.10 or newer

```bash
python --version    # must be 3.10+
```

Download from https://python.org if needed. On macOS, `brew install python` works too.

### 2 — Get the Kynara code

```bash
git clone https://github.com/YOUR_ORG/kynara.git
cd kynara
```

> Ask Vitan for the repo URL if you don't have it.

---

## Tier 0 — Transparent LLM proxy

Kynara wraps any OpenAI-compatible LLM API. Pick **one** of these two upstream options:

| Option | Effort | Notes |
|--------|--------|-------|
| **Groq** (recommended) | 2 min sign-up | Free API key, no GPU needed, very fast |
| **Ollama** | ~5 min install | Runs fully offline, needs ~4 GB RAM |

---

### Option A — Groq (free cloud LLM)

**Step A-1 — Get a free Groq API key**

1. Go to https://console.groq.com
2. Sign up (GitHub login works)
3. Click **API Keys → Create API Key**
4. Copy the key — it starts with `gsk_`

**Step A-2 — Install dependencies**

```bash
cd kynara/kynara-proxy
pip install -r requirements.txt
```

**Step A-3 — Open 3 terminal windows in `kynara/kynara-proxy/`**

**Terminal 1 — Start the mock policy engine**

```bash
python tests/mock_sidecar.py
```

You should see:
```
🔧 Mock Kynara Sidecar running on http://localhost:7070
   DENY list  : ['delete_file', 'drop_table', 'execute_shell', 'send_email']
   APPROVAL   : ['deploy_to_production', 'transfer_funds']
   Everything else → ALLOW
```

**Terminal 2 — Start the Kynara proxy (pointing at Groq)**

```bash
KYNARA_UPSTREAM_URL=https://api.groq.com/openai \
KYNARA_SIDECAR_URL=http://localhost:7070 \
KYNARA_FAIL_OPEN=false \
python main.py
```

On Windows PowerShell:
```powershell
$env:KYNARA_UPSTREAM_URL="https://api.groq.com/openai"
$env:KYNARA_SIDECAR_URL="http://localhost:7070"
$env:KYNARA_FAIL_OPEN="false"
python main.py
```

You should see:
```
INFO  kynara.proxy — Kynara proxy starting | upstream=https://api.groq.com/openai port=8080
```

**Terminal 3 — Run the tests**

```bash
GROQ_API_KEY=gsk_YOUR_KEY_HERE \
TEST_MODEL=llama-3.3-70b-versatile \
python tests/test_tier0.py
```

On Windows PowerShell:
```powershell
$env:GROQ_API_KEY="gsk_YOUR_KEY_HERE"
$env:TEST_MODEL="llama-3.3-70b-versatile"
python tests/test_tier0.py
```

---

### Option B — Ollama (fully offline)

**Step B-1 — Install Ollama**

| OS | Command |
|----|---------|
| macOS | `brew install ollama` |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |
| Windows | Download installer from https://ollama.com/download |

**Step B-2 — Pull a model (one-time, ~2 GB)**

```bash
ollama pull llama3.2
```

Wait for it to finish downloading. You can use `llama3.2` (2 GB) or `mistral` (4 GB).

**Step B-3 — Install dependencies**

```bash
cd kynara/kynara-proxy
pip install -r requirements.txt
```

**Step B-4 — Open 4 terminal windows in `kynara/kynara-proxy/`**

**Terminal 1 — Start Ollama**

```bash
ollama serve
```

**Terminal 2 — Start the mock policy engine**

```bash
python tests/mock_sidecar.py
```

**Terminal 3 — Start the Kynara proxy**

```bash
KYNARA_UPSTREAM_URL=http://localhost:11434 \
KYNARA_SIDECAR_URL=http://localhost:7070 \
KYNARA_FAIL_OPEN=false \
python main.py
```

**Terminal 4 — Run the tests**

```bash
TEST_MODEL=llama3.2 python tests/test_tier0.py
```

---

### Expected Tier 0 results

```
╔══════════════════════════════════════════╗
║   Kynara Tier 0 — Integration Test       ║
╚══════════════════════════════════════════╝

──── TEST 1 — Proxy health ──────────────────────────
  ✅ HTTP 200
──── TEST 2 — Plain LLM call (no tools) ─────────────
  ✅ HTTP 200
  LLM said: hello kynara
──── TEST 3 — Tool call that is ALLOWED (read_file) ──
  ✅ HTTP 200
  read_file was allowed — proxy forwarded to upstream ✓
──── TEST 4 — Tool call that is DENIED (send_email) ──
  ✅ HTTP 403  (expected 403)
  Blocked tools: ['send_email']
  Reason: [Kynara] send_email is in the deny list
──── TEST 5 — Generic endpoint, ALLOWED ──────────────
  ✅ query_database was allowed through
──── TEST 6 — Generic endpoint, DENIED ───────────────
  ✅ HTTP 403  (expected 403)
  delete_file correctly blocked ✓

──── RESULTS ─────────────────────────────────────────
  ✅  Health check
  ✅  Plain LLM passthrough
  ✅  Allowed tool call
  ✅  Denied tool call
  ✅  Generic allowed
  ✅  Generic denied

  6/6 passed
```

**Key thing to observe in Terminal 2 (sidecar):** every tool call appears in real time:
```
  ✅  ALLOW  agent=test-agent-tier0 tool=read_file
  ⛔  DENY   agent=test-agent-tier0 tool=send_email
  ⛔  DENY   agent=test-agent-tier0 tool=delete_file
```

---

## Tier 1 — MCP server wrapper

This is 100% self-contained — no external LLM or API key needed.
Kynara wraps a demo MCP server. The test script acts as the AI agent.

**Step 1 — Install dependencies**

```bash
cd kynara/kynara-mcp-wrapper
pip install -r requirements.txt
```

**Step 2 — Open 3 terminal windows in `kynara/kynara-mcp-wrapper/`**

**Terminal 1 — Start the mock policy engine**

```bash
python tests/mock_sidecar.py
```

> This is the same sidecar used in Tier 0. Same deny list applies.

**Terminal 2 — Start the demo upstream MCP server**

```bash
python tests/demo_mcp_server.py
```

You should see:
```
🔧 Demo MCP Server running on http://localhost:8000/sse
   Tools: get_weather, read_document, send_email*, delete_file*
   (* = blocked by Kynara mock policy)
```

**Terminal 3 — Start the Kynara MCP wrapper**

```bash
KYNARA_UPSTREAM_MCP_URL=http://localhost:8000/sse \
KYNARA_SIDECAR_URL=http://localhost:7070 \
KYNARA_FAIL_OPEN=false \
KYNARA_MCP_WRAPPER_PORT=9090 \
python main.py
```

On Windows PowerShell:
```powershell
$env:KYNARA_UPSTREAM_MCP_URL="http://localhost:8000/sse"
$env:KYNARA_SIDECAR_URL="http://localhost:7070"
$env:KYNARA_FAIL_OPEN="false"
$env:KYNARA_MCP_WRAPPER_PORT="9090"
python main.py
```

Wait for:
```
INFO  kynara.mcp_wrapper — tool_cache.refreshed upstream=http://localhost:8000/sse tools=4
```

**Step 4 — Run the tests (new terminal, same folder)**

```bash
python tests/test_tier1.py
```

---

### Expected Tier 1 results

```
╔══════════════════════════════════════════╗
║   Kynara Tier 1 — Integration Test       ║
╚══════════════════════════════════════════╝

──── TEST 1 — List tools (same as upstream) ──────────
  Tools visible to agent: ['get_weather', 'read_document', 'send_email', 'delete_file']
  ✅ All upstream tools re-exposed by wrapper

──── TEST 2 — Allowed tool: get_weather('London') ────
  Result : 12°C, cloudy
  ✅ Tool executed and result returned

──── TEST 3 — Allowed tool: read_document('/reports/q1.pdf') ──
  Result : [Document content from /reports/q1.pdf]…
  ✅ Tool executed and result returned

──── TEST 4 — DENIED tool: send_email ────────────────
  ✅ Exception: [Kynara] Permission denied for tool 'send_email'. Reason: tool 'send_email' is in the deny list.

──── TEST 5 — DENIED tool: delete_file ───────────────
  ✅ Exception: [Kynara] Permission denied for tool 'delete_file'. Reason: tool 'delete_file' is in the deny list.

──── RESULTS ─────────────────────────────────────────
  ✅  List tools transparent
  ✅  Allowed: get_weather
  ✅  Allowed: read_document
  ✅  Denied: send_email
  ✅  Denied: delete_file

  5/5 passed
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`**
```bash
pip install -r requirements.txt
```

**`ConnectionRefusedError` on sidecar or proxy**
Make sure all required processes are running before you run the test. Check each terminal for errors.

**Tier 0 Test 2 fails (Plain LLM call returns non-200)**
- Groq: double-check your API key and that `TEST_MODEL` is spelled correctly (`llama-3.3-70b-versatile`)
- Ollama: make sure `ollama serve` is running and you pulled the model (`ollama pull llama3.2`)

**Tier 1 Test 2 fails (`Output validation error`)**
Make sure you're using the latest `demo_mcp_server.py` — an older version had `-> str` return type annotations that conflict with newer MCP SDK versions.

**`TypeError: Starlette.__init__() got an unexpected keyword argument 'on_startup'`**
Make sure you're using the latest `kynara-mcp-wrapper/main.py`. Pull the latest code and retry.

**Port already in use**
Something else is running on 7070, 8000, 8080, or 9090. Find and stop it:
```bash
# macOS / Linux
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

---

## What just happened?

When Kynara **blocked** a tool call, your AI agent never reached the upstream service.
The denial happened at the policy layer — the upstream LLM or MCP server saw nothing.

When Kynara **allowed** a tool call, it forwarded transparently. The agent received the real
result exactly as if Kynara wasn't there.

This is the core promise of both tiers: **zero agent code changes, full enforcement**.

---

*Questions? Ping Vitan or open an issue in the repo.*
