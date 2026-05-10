# Kynara — Enterprise AI Agent Permission System

Kynara is a control plane and runtime enforcement layer for AI agents. It answers the
question **"is this agent allowed to do this, right now, on behalf of this user?"** and
produces a tamper-evident audit trail of every decision.

## What's in this repo

```
.
├── backend/          FastAPI control plane: auth, policy engine, audit, billing, SSO, APIs
├── frontend/         React + Vite admin UI (dashboard, policy editor, audit viewer, billing)
├── sdk/              Python SDK — decorator/context-manager/LangChain runtime enforcement
├── sdk-ts/           TypeScript/Node SDK — guarded(), Express middleware, LangChain.js
├── sidecar/          Go decision-cache sidecar — sub-millisecond local enforcement
├── docs/             Architecture, API reference, compliance (SOC 2 / ISO 27001 / GDPR / HIPAA)
├── scripts/          kynara-cli (policy-as-code), offline chain verifier, policy import
├── security/         Threat model, pen-test plan, security audit report
├── trust-center/     Customer-facing compliance evidence page + security.txt
├── e2e/              Playwright end-to-end test suite
├── deploy/terraform/ Terraform modules for AWS ECS/EKS production deployment
├── demo/             Self-contained interactive HTML demo of the whole product
└── docker-compose.yml
```

## Five-minute quickstart

```bash
# 1. Spin up Postgres + Redis + backend + frontend
docker compose up -d

# 2. Run migrations + seed a demo org
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# 3. Open the UI
open http://localhost:5173
# Default login: admin@acme.com / demo-password-123!

# 4a. Install the Python runtime SDK in your agent
pip install -e sdk/

# 4b. Or install the TypeScript/Node SDK
npm install @kynara/sdk
```

### Python SDK — enforce at the tool boundary

```python
from kynara_sdk import Kynara, permission_required

kynara = Kynara(api_key="sk_live_...", base_url="https://api.kynara.dev")

@permission_required("crm.contacts.read", resource_arg="contact_id")
def read_contact(contact_id: str):
    return crm.get(contact_id)
```

If the agent lacks permission, the call raises `PermissionDenied` before any side-effects
occur, and the attempt is recorded in the audit log.

### TypeScript/Node SDK — enforce at the tool boundary

```ts
import { Kynara, guarded, PermissionDenied, ApprovalRequired } from "@kynara/sdk";

const client = Kynara.fromEnv(); // reads KYNARA_BASE_URL, KYNARA_API_KEY, KYNARA_AGENT_ID

const issueRefund = guarded({
  client,
  action: "payments.refund.issue",
  resource: (refundId: string, amountCents: number) => ({
    type: "payment.refund",
    id: refundId,
    attrs: { amount_cents: amountCents, currency: "USD" },
  }),
}, async (refundId: string, amountCents: number) => {
  return await processRefund(refundId, amountCents);
});
```

## Core concepts

- **Subject** — the acting principal. Usually `agent:<id>` acting `on_behalf_of user:<id>`.
- **Action** — a namespaced verb like `crm.contacts.read` or `payments.refund.issue`.
- **Resource** — the target of the action, with attributes (owner, classification, region).
- **Policy** — a rule `(subject, action, resource, context) → allow | deny | require_approval`.
- **Decision** — the audited, hash-chained output of the policy engine for one check.
- **JIT Grant** — a time-bound, break-glass permission elevation with a justification and ticket link.

The data model is RBAC + ABAC: roles grant capabilities, and conditions on attributes
(time of day, data classification, IP, approval state) gate the final decision.

## Feature matrix

| Claim | What's in this repo |
|---|---|
| Real auth | Argon2id password hashing, JWT access + rotating refresh tokens, API keys with per-key scopes + rate limits |
| Real DB | Postgres, SQLAlchemy 2.x, Alembic migrations, row-level multi-tenancy |
| Python SDK | Decorator + context-manager + LangChain callback; fail-closed, in-process decision cache |
| TypeScript SDK | `guarded()` wrapper + Express middleware + LangChain.js callback; npm `@kynara/sdk` |
| Agent frameworks | LangChain, LangGraph, LangChain.js, Microsoft AutoGen, CrewAI, OpenAI Assistants API, Anthropic tool use |
| Go sidecar | Sub-millisecond local evaluation; JWS Ed25519–signed policy bundles; streams decisions back to central API |
| Policy-as-code CLI | `scripts/kynara-cli.py` — pull/push/diff/verify policy bundles; designed for git + CI |
| Real SSO | Okta SAML 2.0 + OIDC flows, Azure AD, Google Workspace; SCIM 2.0 user provisioning |
| Real billing | Stripe customer/subscription/usage metering, invoice webhooks, seat + decision quotas, trial enforcement |
| Superadmin | Platform-wide org and user management; superadmin can create orgs and invite members to any org |
| JIT grants | Time-bound break-glass permission elevation with justification + ticket link; full audit chain |
| Policy replay | Retroactive policy impact simulation against up to 30 days / 100k historical decisions |
| Guardrails | Threshold-based auto-revocation; webhook event ingestion from agent runtimes |
| Approval flows | Dedicated approvals queue with polling + webhooks; expiry, justification, escalation |
| Webhook subscriptions | Full CRUD for webhook endpoints; HMAC-signed delivery; outbox fan-out |
| Scope Catalog | Tool registry (renamed from Tools) with risk levels, input schemas, scope picker in role editor |
| Tamper-evident audit | Hash-chained (Merkle) audit log, append-only trigger, integrity verification, CSV export |
| SIEM integration | Polling cursor for Splunk, Datadog, Elastic; SIEM-ready JSON event format |
| Monitoring | Structured JSON logs, OpenTelemetry traces + metrics, Prometheus exporter |
| Pen-test | OWASP ASVS + OWASP LLM Top 10 checklist, runnable script harness |
| APIs | OpenAPI 3.1 spec; versioned under `/api/v1`; 30+ paths |
| CI/CD | GitHub Actions: lint, type-check, bandit, migrate, pytest, Playwright E2E, cosign container signing |
| Terraform | AWS ECS Fargate + EKS modules under `deploy/terraform/` |
| Trust Center | Customer-facing compliance evidence page at `/trust`; `/.well-known/security.txt` |
| Compliance | SOC 2 Type II control mapping, ISO 27001 Annex A mapping, GDPR DPA template, HIPAA overview, DPIA |

## Agent framework integrations

### LangChain / LangGraph (Python)

```python
from langchain.agents import AgentExecutor
from kynara_sdk.langchain import KynaraCallbackHandler

executor = AgentExecutor(
    agent=my_agent, tools=my_tools,
    callbacks=[KynaraCallbackHandler(kynara, agent_id=AGENT_ID)],
)
```

### Microsoft AutoGen (Python)

```python
# Wrap each AutoGen-registered tool with kynara.enforce() before execution.
# See sdk/examples/autogen_agent.py for the full pattern.
```

### CrewAI (Python)

```python
# Apply the kynara_guard decorator to BaseTool._run.
# See sdk/examples/crewai_agent.py for the full pattern.
```

### OpenAI Assistants / Chat Completions (Python)

```python
# Gate each tool_call dispatch through kynara.enforce() before calling the implementation.
# See sdk/examples/openai_assistants.py for the full pattern.
```

### Anthropic tool use (Python)

```python
# Intercept ToolUseBlock before executing the tool function.
# See sdk/examples/anthropic_tool_use.py for the full pattern.
```

### LangChain.js (TypeScript)

```ts
import { KynaraCallbackHandler } from "@kynara/sdk/langchain";
const executor = new AgentExecutor({
  agent, tools,
  callbacks: [new KynaraCallbackHandler(client, "agent_crm_assistant")],
});
```

### Express middleware (TypeScript)

```ts
import { requirePermission } from "@kynara/sdk/express";
app.post("/refunds/:id",
  requirePermission({
    client,
    action: "payments.refund.issue",
    resource: (req) => ({ type: "payment.refund", id: req.params.id, attrs: req.body }),
  }),
  refundController);
```

## Sub-millisecond enforcement: the sidecar

For high-throughput workloads, run the Go sidecar instead of calling the central API directly.

```bash
docker run --rm -p 7070:7070 \
  -e KYNARA_API_KEY=$KEY \
  -e KYNARA_BASE_URL=https://api.kynara.dev \
  ghcr.io/kynara/decision-cache:latest
```

The sidecar fetches a JWS Ed25519–signed policy bundle every 30 seconds, evaluates decisions
locally at sub-millisecond latency, and streams decision telemetry back to the central audit
log in 5-second batches. Point your SDK at `http://localhost:7070`.

## Policy-as-code

Manage policies through git using the CLI:

```bash
# Pull the live policy bundle to a file
python scripts/kynara-cli.py pull --out policies.json

# Diff a local change against live
python scripts/kynara-cli.py diff --bundle policies.json

# Push and apply (dry-run first)
python scripts/kynara-cli.py push --bundle policies.json --dry-run
python scripts/kynara-cli.py push --bundle policies.json

# Verify bundle checksum integrity
python scripts/kynara-cli.py verify --bundle policies.json
```

Add a CI step to run `diff` on every PR to show policy impact before merging.

## JIT (Just-in-Time) grants

Grant a temporary permission elevation for break-glass scenarios:

```bash
POST /api/v1/jit-grants
{
  "scope": "crm:write",
  "duration_minutes": 120,
  "justification": "Investigating prod escalation",
  "ticket_url": "https://jira.example.com/TICKET-42"
}
```

Every grant creation and revocation is recorded in the audit chain. Grants auto-expire
after the requested duration.

## Policy historical replay

Before deploying a new or modified policy, simulate its impact against real historical
decisions:

```bash
POST /api/v1/policy-replay
{
  "policy": { "effect": "deny", "actions": ["payments.refund.issue"], "condition": {...} },
  "lookback_days": 30
}
# Returns: { "would_flip": 47, "allow→deny": 34, "allow→require_approval": 13, ... }
```

Results cap at 30 days × 100k events. For larger windows, use the offline replayer in
`scripts/kynara-import.py`.

## What "real" means here

| Claim | What's in this repo |
|---|---|
| Real auth | Argon2id with server-side pepper; JWT (15 min) + rotating opaque refresh tokens (30 d) with reuse detection |
| Real DB | Postgres, SQLAlchemy 2.x, Alembic migrations, RLS policies on every tenant-scoped table, append-only trigger on `audit_events` |
| Real runtime enforcement | Python SDK with decorator + middleware + context manager; TypeScript SDK with `guarded()` + Express middleware; Go sidecar with local evaluation |
| Real SSO | Okta SAML 2.0 + OIDC flows, Azure AD, Google Workspace; SCIM 2.0 user provisioning stubs |
| Real billing | Stripe customer/subscription/usage metering, invoice webhooks; seat limits, decision quotas, trial period enforcement |
| Security audit | Hash-chained (Merkle) audit log, integrity verification job, offline verifier script |
| Monitoring | Structured JSON logs, OpenTelemetry traces + metrics, Prometheus exporter |
| Pen-test | OWASP ASVS + OWASP LLM Top 10 checklist, runnable script harness |
| APIs | OpenAPI 3.1 spec, versioned under `/api/v1`, 30+ paths |
| Compliance | SOC 2 Type II control mapping, ISO 27001 Annex A mapping, GDPR DPA template, HIPAA overview, DPIA |

## Licensing

Source-available under the Business Source License 1.1. See `LICENSE`.
