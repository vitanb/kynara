# Kynara Integration Guide

This guide walks you through wiring Kynara into an AI agent's runtime so that every tool call, data read, and side-effecting action gets checked against your organization's policies. It covers the Python SDK, the TypeScript/Node SDK, all supported agent frameworks, the Go sidecar, policy-as-code, JIT grants, policy replay, and approval flows.

## 1. Concepts in 60 seconds

- **Principal** — the identity making a request. Usually an `agent`, sometimes a `user` (for approval flows) or `api_key`.
- **Action** — dotted string like `crm.contacts.read`, `email.send`, `payments.refund.issue`.
- **Resource** — `{ type, id, attrs }`. The `attrs` field is what ABAC policies inspect (classification, owner, region, amount, etc.).
- **Context** — ambient facts: time, IP country, request origin, trace ID.
- **Decision** — one of `allow`, `deny`, `require_approval`. Approvals return an `approval_url` that routes to a human.
- **JIT Grant** — a time-bound, break-glass elevation that temporarily widens an agent's effective scopes.

Policies are matched in priority order (`0` highest, `1000` lowest). The first policy whose conditions all evaluate true wins. If none match, the default is `deny` (fail-closed).

---

## 2. Python SDK

### Install

```bash
pip install kynara-sdk
```

Environment variables read by the SDK:

| Var | Default | Purpose |
|---|---|---|
| `KYNARA_BASE_URL` | `https://api.kynara.example.com` | API endpoint |
| `KYNARA_API_KEY` | — | `sk_live_…` key for machine auth |
| `KYNARA_AGENT_ID` | — | Subject for agent checks |
| `KYNARA_FAIL_CLOSED` | `true` | Deny on network error |

### Decorator

```python
from kynara_sdk import Kynara, permission_required
from kynara_sdk.context import set_current_kynara

set_current_kynara(Kynara.from_env())

@permission_required(
    action="crm.contacts.read",
    resource_arg="contact_id",
    resource_type="crm.contact",
    resource_attrs=lambda contact_id: {"classification": "pii"},
    context_fn=lambda: {"ip_country": request.country},
)
def read_contact(contact_id: str) -> dict:
    return crm_client.get_contact(contact_id)
```

If Kynara returns `deny`, the decorator raises `PermissionDenied`. If it returns `require_approval`, it raises `ApprovalRequired` with the `approval_url`.

### Context manager

```python
with kynara.guard(
    "payments.refund.issue",
    resource={"type": "payment", "id": payment_id, "attrs": {"amount_cents": 50000}},
) as grant:
    result = issue_refund(payment_id)
    # grant auto-confirms success on clean exit; error outcome auto-recorded on raise
```

### Manual check

```python
decision = kynara.check(
    subject=("agent", os.environ["KYNARA_AGENT_ID"]),
    action="payments.refund.issue",
    resource={"type": "payment.refund", "id": refund_id, "attrs": {"amount_cents": amount_cents}},
    context={"session_id": session_id},
)
if decision.effect == "allow":
    process_refund(refund_id)
elif decision.effect == "require_approval":
    notify_approver(decision.approval_url)
else:
    log_denied(decision.reason)
```

---

## 3. TypeScript / Node SDK

### Install

```bash
npm install @kynara/sdk
```

Environment variables read by the SDK (same as Python):
`KYNARA_BASE_URL`, `KYNARA_API_KEY`, `KYNARA_AGENT_ID`.

### `guarded()` wrapper

```ts
import { Kynara, guarded, PermissionDenied, ApprovalRequired } from "@kynara/sdk";

const client = Kynara.fromEnv();

const issueRefund = guarded({
  client,
  action: "payments.refund.issue",
  resource: (refundId: string, amountCents: number) => ({
    type: "payment.refund",
    id: refundId,
    attrs: { amount_cents: amountCents, currency: "USD" },
  }),
  context: () => ({ ip_country: "US" }),
}, async (refundId: string, amountCents: number) => {
  return await processRefund(refundId, amountCents);
});

try {
  await issueRefund("r_123", 500_00);
} catch (e) {
  if (e instanceof ApprovalRequired) notifyApprover(e.approvalUrl);
  else if (e instanceof PermissionDenied) auditDeny(e.decision.reason);
  else throw e;
}
```

### Express middleware

```ts
import { requirePermission } from "@kynara/sdk/express";

app.post("/refunds/:id",
  requirePermission({
    client,
    action: "payments.refund.issue",
    resource: (req) => ({
      type: "payment.refund",
      id: req.params.id,
      attrs: { amount_cents: req.body.amount_cents, currency: "USD" },
    }),
    context: (req) => ({ ip: req.ip }),
  }),
  refundController,
);
```

`deny` returns `403`; `require_approval` returns `202` with `{ approval_url }` in the body.

---

## 4. Agent Framework Integrations

### LangChain / LangGraph (Python)

Register the callback handler once — it intercepts every `on_tool_start` event:

```python
from langchain.agents import AgentExecutor
from kynara_sdk.langchain import KynaraCallbackHandler

executor = AgentExecutor(
    agent=my_agent,
    tools=my_tools,
    callbacks=[KynaraCallbackHandler(kynara, agent_id=AGENT_ID)],
)
```

The callback maps `on_tool_start` → `kynara.check(...)` and raises on `deny`. `ApprovalRequired` is surfaced as a `ToolException` with the approval URL attached.

### LangChain.js (TypeScript)

```ts
import { KynaraCallbackHandler } from "@kynara/sdk/langchain";

const executor = new AgentExecutor({
  agent,
  tools,
  callbacks: [new KynaraCallbackHandler(client, "agent_crm_assistant")],
});
```

### Microsoft AutoGen (Python)

Wrap each registered tool function before handing it to AutoGen:

```python
import functools
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired

kynara = Kynara.from_env()

def kynara_tool(*, action: str, resource_factory):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                kynara.enforce(
                    subject=("agent", os.environ["KYNARA_AGENT_ID"]),
                    action=action,
                    resource=resource_factory(*args, **kwargs),
                    context={"framework": "autogen"},
                )
            except PermissionDenied as e:
                return {"error": "permission_denied", "reason": e.decision.reason}
            except ApprovalRequired as e:
                return {"error": "approval_required", "approval_url": e.decision.approval_url}
            return fn(*args, **kwargs)
        return wrapper
    return deco

@kynara_tool(
    action="crm.contacts.read",
    resource_factory=lambda contact_id: {"type": "crm.contact", "id": contact_id, "attrs": {"classification": "pii"}},
)
def crm_read(contact_id: str) -> dict:
    return {"id": contact_id, "name": "Demo"}
```

See `sdk/examples/autogen_agent.py` for the complete working example with `GroupChat`.

### CrewAI (Python)

Apply `kynara_guard` to `BaseTool._run`:

```python
from crewai.tools import BaseTool
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired

kynara = Kynara.from_env()

def kynara_guard(action: str, resource_factory):
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(self, *args, **kwargs):
            try:
                kynara.enforce(
                    subject=("agent", os.environ["KYNARA_AGENT_ID"]),
                    action=action,
                    resource=resource_factory(*args, **kwargs),
                    context={"framework": "crewai", "tool": self.name},
                )
            except PermissionDenied as e:
                return f"DENIED ({e.decision.reason})"
            except ApprovalRequired as e:
                return f"NEEDS APPROVAL: {e.decision.approval_url}"
            return fn(self, *args, **kwargs)
        return wrapped
    return deco

class RefundTool(BaseTool):
    name: str = "payments_refund_issue"
    description: str = "Issue a refund"

    @kynara_guard(
        action="payments.refund.issue",
        resource_factory=lambda refund_id, amount_cents: {
            "type": "payment.refund", "id": refund_id,
            "attrs": {"amount_cents": amount_cents, "currency": "USD"},
        },
    )
    def _run(self, refund_id: str, amount_cents: int) -> str:
        return f"refund {refund_id}: issued"
```

See `sdk/examples/crewai_agent.py` for the complete working example with a `Crew`.

### OpenAI Assistants / Chat Completions (Python)

Gate each tool-call dispatch through `kynara.enforce()` before calling the implementation:

```python
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired
import json

kynara = Kynara.from_env()

def dispatch_tool_call(name: str, args: dict) -> str:
    try:
        kynara.enforce(
            subject=("agent", os.environ["KYNARA_AGENT_ID"]),
            action=ACTION_FOR[name],
            resource=RESOURCE_FOR[name](args),
            context={"framework": "openai-assistants"},
        )
    except PermissionDenied as e:
        return json.dumps({"error": "permission_denied", "reason": e.decision.reason})
    except ApprovalRequired as e:
        return json.dumps({"error": "approval_required", "approval_url": e.decision.approval_url})
    return json.dumps(TOOL_IMPL[name](**args))
```

See `sdk/examples/openai_assistants.py` for the complete agentic loop.

### Anthropic Tool Use (Python)

See `sdk/examples/anthropic_tool_use.py` for intercepting `ToolUseBlock` messages before dispatching to tool implementations.

---

## 5. Go Sidecar (sub-millisecond enforcement)

For high-throughput agent workloads where per-action API latency is a bottleneck:

```bash
docker run --rm -p 7070:7070 \
  -e KYNARA_API_KEY=$KEY \
  -e KYNARA_BASE_URL=https://api.kynara.example.com \
  ghcr.io/kynara/decision-cache:latest
```

Point your SDK at the sidecar:

```python
kynara = Kynara(api_key=KEY, base_url="http://localhost:7070", agent_id=AGENT_ID)
```

The sidecar fetches a JWS Ed25519–signed policy bundle every 30 seconds, evaluates locally, and streams decisions back to the central audit log in 5-second batches. Latency: p95 < 1ms vs. p95 ≈ 8ms for direct API calls.

**Note:** `require_approval` decisions are never cached or evaluated locally — they always go to the central API so the approval workflow functions correctly.

---

## 6. Caching and latency

The Python and TypeScript SDKs cache `allow` decisions in-process for `ttl_seconds` (default 5s, configurable per policy). `require_approval` decisions are never cached — every request gets a fresh decision.

| Path | p95 latency |
|---|---|
| SDK in-process cache hit | ~200µs |
| Go sidecar (local bundle) | < 1ms |
| Central API over LAN | < 8ms |
| Central API over WAN | < 30ms |

---

## 7. Approval flows

When a decision returns `require_approval`, your agent should:

1. Pause the current tool call.
2. Present the `approval_url` to the requesting human (Slack thread, app UI, email).
3. Poll `GET /api/v1/approvals/{approval_id}` or subscribe to webhooks (`decision.approved`, `decision.denied`).
4. Resume or abort based on the outcome.

SLA: approvals expire after 24 hours by default (configurable per policy).

```python
try:
    kynara.enforce(action="payments.refund.issue", ...)
except ApprovalRequired as e:
    send_slack_message(channel, f"Approval needed: {e.decision.approval_url}")
    # poll or wait for webhook
    outcome = poll_approval(e.decision.decision_id)
    if outcome == "approved":
        process_refund(...)
```

---

## 8. JIT (Just-in-Time) grants

For break-glass scenarios where an operator needs temporary elevated access:

```bash
POST /api/v1/jit-grants
Authorization: Bearer <admin-token>

{
  "scope": "crm:write",
  "duration_minutes": 120,
  "justification": "Investigating prod escalation TICKET-42",
  "ticket_url": "https://jira.example.com/TICKET-42"
}
```

The grant is active immediately. The policy engine checks active grants before the RBAC intersection step, widening the agent's effective scopes for the grant duration. Every grant creation and revocation is recorded in the audit chain.

To revoke early:

```bash
DELETE /api/v1/jit-grants/{grant_id}
```

---

## 9. Policy historical replay

Before deploying a policy change, simulate its impact against real historical decisions:

```bash
POST /api/v1/policy-replay
Authorization: Bearer <admin-token>

{
  "policy": {
    "effect": "require_approval",
    "actions": ["payments.refund.issue"],
    "condition": {
      "op": "not",
      "args": [{ "op": "time_between", "args": ["ctx.context.time", "09:00", "18:00"] }]
    }
  },
  "lookback_days": 14
}
```

Response:

```json
{
  "total_events": 1847,
  "flipped": 134,
  "allow_to_deny": 0,
  "allow_to_require_approval": 134,
  "deny_to_allow": 0,
  "sample_affected_decision_ids": ["d_abc123", "d_def456"]
}
```

Results cap at 30 days × 100k events. For larger windows, use the offline replayer:

```bash
python scripts/kynara-import.py --bundle policies.json --audit-export audit.parquet
```

---

## 10. Policy-as-code (GitOps)

Manage policies through git using the CLI:

```bash
# Authenticate via env vars
export KYNARA_BASE_URL=https://api.kynara.example.com
export KYNARA_API_KEY=sk_live_...

# Pull the live bundle to a JSON file
python scripts/kynara-cli.py pull --out policies.json

# Check what a local change would flip in production
python scripts/kynara-cli.py diff --bundle policies.json

# Apply (dry-run to preview, then for real)
python scripts/kynara-cli.py push --bundle policies.json --dry-run
python scripts/kynara-cli.py push --bundle policies.json

# Verify the bundle checksum matches the server
python scripts/kynara-cli.py verify --bundle policies.json
```

**Recommended CI pattern** (GitHub Actions):

```yaml
- name: Policy diff
  run: python scripts/kynara-cli.py diff --bundle policies.json
  # Fails if bundle checksum doesn't match; diff output posted to PR as comment
```

---

## 11. Audit log access

Every decision is written to a hash-chained audit log. Compliance teams can:

- Filter by actor, event type, outcome, and time range via `GET /api/v1/audit/events`.
- Verify the entire chain's integrity via `POST /api/v1/audit/verify`.
- Export to CSV via `GET /api/v1/audit/events?format=csv`.
- Consume via SIEM polling cursor: `GET /api/v1/audit/events?after_cursor=<cursor>` (returns `next_cursor` for stateless pagination into Splunk, Datadog, or Elastic).
- Verify offline using `scripts/verify_chain_offline.py` — no API dependency.

---

## 12. Webhooks

Subscribe to events at **Settings → Webhooks**. Each delivery is HMAC-signed with `X-Kynara-Signature: sha256=v1,<hex>`.

> **HTTPS only.** Webhook URLs must use `https://`. HTTP URLs and URLs resolving to private/internal addresses are rejected at creation time.

```python
import hmac, hashlib

def verify_webhook(secret: str, body: bytes, signature_header: str) -> bool:
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    expected = "sha256=v1," + computed
    return hmac.compare_digest(expected, signature_header)
```

**Available events:**

| Event | When |
|---|---|
| `decision.allowed` | Agent action permitted by policy |
| `decision.denied` | Agent action blocked by policy |
| `decision.approval_requested` | Policy returned `require_approval` |
| `decision.approved` | Human approved a pending request |
| `decision.rejected` | Human rejected a pending approval |
| `agent.created` | A new agent was registered |
| `agent.killed` | Kill switch activated on an agent |
| `agent.permissions_changed` | A role assignment or JIT grant changed an agent's effective scopes |
| `policy.changed` | Policy created, updated, or deleted |
| `audit.chain_broken` | Integrity verifier detected a chain gap |
| `approval.expired` | A pending approval timed out (default 24 h) |

Subscribe via the API:

```bash
POST /api/v1/webhooks
{
  "url": "https://your-app.example.com/kynara-events",
  "events": ["decision.denied", "agent.killed", "audit.chain_broken"]
}
```

---

## 13. Production checklist

- [ ] Set `JWT_SECRET` to a random 32+ char string (`openssl rand -hex 32`) — the default placeholder is rejected at startup in production.
- [ ] Set `PASSWORD_PEPPER` to a strong random value — the default `change-me-in-prod` is not enforced at startup but leaves passwords vulnerable.
- [ ] Set `METRICS_SECRET` (`openssl rand -hex 32`) — the `/metrics` endpoint returns 403 for all requests unless this is set; configure your Prometheus scraper to send `X-Metrics-Token: <value>`.
- [ ] After rotating `JWT_SECRET`, revoke and re-issue all API keys — HMAC-keyed hashes are derived from the server secret, so existing keys become invalid after rotation.
- [ ] Rotate the server-side JWT secret and pepper on go-live.
- [ ] Configure SSO so human sign-in is IdP-backed.
- [ ] Enable Stripe metering for usage-based billing.
- [ ] Set `KYNARA_FAIL_CLOSED=true` in every runtime.
- [ ] Add `audit.chain_broken` alerts to PagerDuty.
- [ ] Run `POST /api/v1/audit/verify` on a cron (weekly).
- [ ] Subscribe to `agent.permissions_changed` and `agent.killed` webhooks.
- [ ] Configure SIEM polling cursor for Splunk/Datadog/Elastic.
- [ ] Load-test `/decisions/check` at 2× expected peak.
- [ ] Export backups of `policies`, `roles`, and `audit_events` nightly.
- [ ] Deploy Go sidecar if p95 decision latency must be < 1ms.
- [ ] Set up `kynara-cli.py` in CI for policy-as-code diff on every PR.
- [ ] Verify webhook endpoints use `https://` — HTTP URLs are rejected.
