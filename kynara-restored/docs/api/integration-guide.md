# Kynara Integration Guide

This guide walks you through wiring Kynara into an AI agent's runtime so that every tool call, data read, and side-effecting action gets checked against your organization's policies.

## 1. Concepts in 60 seconds

- **Principal** — the identity making a request. Usually an `agent`, sometimes a `user` (for approval flows) or `api_key`.
- **Action** — dotted string like `crm.contacts.read`, `email.send`, `payments.refund.issue`.
- **Resource** — `{ type, id, attrs }`. The `attrs` field is what ABAC policies inspect (classification, owner, region, amount, etc.).
- **Context** — ambient facts: time, IP country, request origin, trace ID.
- **Decision** — one of `allow`, `deny`, `require_approval`. Approvals return an `approval_url` that routes to a human.

Policies are matched in priority order (`0` highest, `1000` lowest). The first policy whose conditions all evaluate true wins. If none match, the default is `deny` (fail-closed).

## 2. Install the Python SDK

```bash
pip install kynara-sdk
```

Environment variables read by the SDK:

| Var | Default | Purpose |
|---|---|---|
| `KYNARA_BASE_URL` | `https://kynara.example.com` | API endpoint |
| `KYNARA_API_KEY` | — | `sk_live_…` key for machine auth |
| `KYNARA_AGENT_ID` | — | Subject for agent checks |
| `KYNARA_FAIL_CLOSED` | `true` | Deny on network error |

## 3. Enforce at the tool boundary

Wrap every tool-callable function with `@permission_required`:

```python
from kynara_sdk import Kynara, permission_required

kynara = Kynara.from_env()

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

If Kynara returns `deny`, the decorator raises `PermissionDenied`. If it returns `require_approval`, it raises `ApprovalRequired` with the `approval_url` — surface this to your agent so it can notify the requesting user.

## 4. Manual checks

When you need finer control (e.g., two-step flows, batch decisions):

```python
decision = kynara.check(
    subject=("agent", os.environ["KYNARA_AGENT_ID"]),
    action="payments.refund.issue",
    resource={
        "type": "payment.refund",
        "id": refund_id,
        "attrs": {"amount_cents": amount_cents, "currency": "USD"},
    },
    context={"session_id": session_id},
)
if decision.effect == "allow":
    process_refund(refund_id)
elif decision.effect == "require_approval":
    notify_approver(decision.approval_url)
else:
    log_denied(decision.reason)
```

## 5. LangChain / LangGraph integration

Register the callback handler once; it intercepts every tool call:

```python
from langchain.agents import AgentExecutor
from kynara_sdk.langchain import KynaraCallbackHandler

executor = AgentExecutor(
    agent=my_agent,
    tools=my_tools,
    callbacks=[KynaraCallbackHandler(kynara, agent_id=AGENT_ID)],
)
```

The callback maps `on_tool_start` → `kynara.check(...)` and raises on `deny`. Approval-required responses are surfaced as a `ToolException` with the approval URL attached, so the agent can route the request appropriately instead of silently failing.

## 6. Caching and latency

The SDK caches `allow` decisions in-process for `ttl_seconds` (default 5s, configurable per policy). `require_approval` decisions are never cached — every request gets a fresh decision because approvers may have revoked earlier consent. On cache hit, enforcement adds roughly 200µs. On cache miss over LAN, p95 is under 8ms.

For sub-millisecond enforcement, run the sidecar:

```bash
docker run --rm -p 7070:7070 \
  -e KYNARA_API_KEY=$KEY \
  ghcr.io/kynara/decision-cache:latest
```

Point the SDK at `http://localhost:7070` and it will pull policy bundles every 30s and evaluate locally.

## 7. Approval flows

When a decision returns `require_approval`, your agent should:

1. Pause the current tool call.
2. Present the `approval_url` to the requesting human via whatever channel they're using (Slack thread, app UI, email).
3. Poll `GET /api/v1/decisions/{decision_id}` or subscribe to webhooks (`decision.approved`, `decision.denied`).
4. Resume or abort based on the outcome.

SLA: approvals expire after 24 hours by default (configurable per policy).

## 8. Audit log access

Every decision is written to a hash-chained audit log. Compliance teams can:

- Filter by actor, event type, outcome, and time range via `GET /api/v1/audit/events`.
- Verify the entire chain's integrity via `POST /api/v1/audit/verify`.
- Export to S3/GCS with nightly signed Parquet snapshots (see Enterprise runbook).

## 9. Webhooks

Subscribe to events at `Settings → Webhooks`. Each delivery is HMAC-signed with `X-Kynara-Signature` (SHA-256, sha256=… format). Verify:

```python
import hmac, hashlib
computed = hmac.new(secret, body, hashlib.sha256).hexdigest()
assert hmac.compare_digest("sha256=" + computed, request.headers["X-Kynara-Signature"])
```

Events: `decision.denied`, `decision.approval_requested`, `decision.approved`, `agent.killed`, `policy.changed`, `audit.chain_broken`.

## 10. Production checklist

- [ ] Rotate the server-side JWT secret and pepper on go-live.
- [ ] Configure SSO so human sign-in is IdP-backed.
- [ ] Enable Stripe metering for usage-based billing.
- [ ] Set `KYNARA_FAIL_CLOSED=true` in every runtime.
- [ ] Add `audit.chain_broken` alerts to PagerDuty.
- [ ] Run `POST /api/v1/audit/verify` on a cron (weekly).
- [ ] Load-test `/decisions/check` at 2× expected peak.
- [ ] Export backups of `policies`, `roles`, and `audit_events` nightly.
