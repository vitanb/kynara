# Kynara Architecture Overview

## System goals

Kynara exists to let enterprises deploy AI agents in production without surrendering auditability or control. The central promise is:

> No AI agent can take an action that a reasonably careful security engineer would not have approved, and no action — approved or denied — is taken without an auditable record.

That promise drives three non-negotiable properties:

1. **Central, fail-closed authorization.** Agents call out to the policy engine before every side effect. When the policy engine is unreachable, the default answer is deny.
2. **Bounded-authority rule.** An agent's effective permissions are the intersection of the role assigned to the agent *and* the role of the supervising human. An agent can never exceed the authority of the human it acts for.
3. **Tamper-evident audit.** Every decision and every admin change is written to an append-only log with SHA-256 chaining. Any tampering is detectable by replaying the chain.

## Components

### Frontend (React + Vite + TypeScript)

A single-page app under `/frontend`. Authenticates humans via password or SSO (Okta, Azure AD, Google Workspace). Key pages:

- **Dashboard** — stat cards (agents, policies, decisions, chain status), 24h decisions chart, onboarding checklist.
- **Agents** — agent registry, kill switch, role assignments, access-summary API.
- **Scope Catalog** — tool registry (formerly "Tools") grouped by namespace with risk pills and scope picker.
- **Policies** — policy list, ABAC condition editor, integrated live simulator (runs against the live engine without side effects), policy replay against historical decisions.
- **Audit** — filterable log, chain verification banner, CSV export.
- **Approvals** — queue of pending `require_approval` decisions; approve/deny with justification.
- **Guardrails** — webhook ingestion integrations and threshold rules for auto-revocation.
- **Billing** — plan, seat usage, decision quota, 30-day bar chart, Stripe checkout, invoice history.
- **Settings** — members, pending invites, API keys (CRUD), SSO connections, org defaults, danger zone (rotate keys, revoke sessions, delete org).
- **JIT Grants** — create and revoke time-bound break-glass permission elevations.
- **How It Works** — in-app explainer for new users.
- **Landing page** (`/`) — public marketing page.
- **Pricing page** — subscription tiers with feature comparison.
- **Docs** (`/docs`) — in-app documentation hub.
- **Trust Center** (`/trust`) — customer-facing compliance evidence page (SOC 2, ISO 27001, HIPAA, GDPR).

The UI uses Google's light design system and is fully role-gated — viewers cannot modify policies; developers cannot manage members.

### Backend (FastAPI + async SQLAlchemy)

Under `/backend/app`. Async Python 3.12. Key modules:

- `auth` — password hashing (Argon2id + pepper), JWT + rotating refresh, session model.
- `sso` — Okta OIDC (PKCE) and SAML 2.0 SP via `python3-saml`; SCIM 2.0 user provisioning.
- `sso_connections` — multiple SSO provider connections per org.
- `policy` — pure policy engine (`engine.py`) and a service wrapper (`service.py`) that applies hard gates (disabled agent, org mismatch), RBAC intersection, and the ABAC condition tree.
- `audit` — hash-chained writes and a verification endpoint; CSV export; SIEM polling cursor.
- `billing` — Stripe usage metering, checkout, webhook verification; seat + decision quota enforcement; trial period tracking.
- `webhooks` — webhook endpoint CRUD, outbox fan-out, HMAC-signed delivery.
- `jit_grants` — time-bound break-glass grants with justification, ticket link, and auto-expiry.
- `policy_replay` — retroactive simulation of proposed policies against historical audit events.
- `policy_bundle` — signed bundle generation for the Go sidecar.
- `guardrails` — event ingestion webhook, threshold rule evaluation, auto-revocation.
- `approvals` — approval lifecycle (create, approve, deny, expire).
- `invites` — email-based member invitation with role pre-assignment; pending invite UI.
- `admin` — superadmin endpoints: platform-wide org list/create, user management across orgs.
- `org` — org settings, org switcher, role-restricted member management, duplicate org guard.
- `api_keys` — API key CRUD with per-key scopes and rate limits.
- `contact` — in-app contact form with MailChannels/SMTP delivery.
- `middleware` — security headers, request context, body-size limits, slowapi rate limits.
- `api/v1` — versioned REST endpoints (30+ paths).

### Database (PostgreSQL 15+)

Multi-tenant. Every tenant-scoped table carries `org_id` and has a Row-Level Security policy that requires `current_setting('app.org_id')` to match. Sessions opened by the application set the GUC on first use; background jobs use a special service identity.

The `audit_events` table is append-only by trigger — attempted `UPDATE` or `DELETE` raises `P0001`.

New tables since initial release:

| Table | Purpose |
|---|---|
| `webhook_endpoints` | Registered delivery URLs per org |
| `webhook_outbox` | Fan-out queue for signed delivery |
| `jit_grants` | Time-bound break-glass grants |
| `sso_connections` | Multiple IdP connections per org |
| `invites` | Pending member invitations |
| `plan_entitlements` | Seat limits, decision quotas, trial dates |
| `superadmin_users` | Platform-level superadmin flag |

### Cache (Redis)

Short-lived decision cache (default 5s TTL). `require_approval` and `deny` decisions are never cached.

Also used as the rate-limit token bucket (slowapi) and the webhook outbox queue.

### Python SDK

Under `/sdk`. Provides:

- `Kynara(...)` client with retries, in-process cache, and `fail_closed=True` default.
- `@permission_required(...)` decorator (sync + async).
- `kynara.guard(...)` context manager.
- `KynaraCallbackHandler` for LangChain/LangGraph `on_tool_start`.
- Context-managed guards and typed errors (`PermissionDenied`, `ApprovalRequired`, `KynaraUnavailable`).
- Framework examples: LangChain, AutoGen, CrewAI, OpenAI Assistants, Anthropic tool use (under `sdk/examples/`).

### TypeScript / Node SDK

Under `/sdk-ts`. Provides:

- `Kynara.fromEnv()` client (reads `KYNARA_BASE_URL`, `KYNARA_API_KEY`, `KYNARA_AGENT_ID`).
- `guarded(opts, fn)` — wraps any async function; raises `PermissionDenied` or `ApprovalRequired`.
- `requirePermission(opts)` — Express middleware for route-level enforcement.
- `KynaraCallbackHandler` for LangChain.js `AgentExecutor`.
- Fail-closed by default; identical semantics to the Python SDK.
- Published as `@kynara/sdk` on npm.

### Go Decision-Cache Sidecar

Under `/sidecar`. A lightweight Go service that:

1. GETs `/api/v1/policy-bundle` from the central API on startup and every 30 seconds.
2. Verifies the JWS signature on the bundle (Ed25519 over canonical JSON).
3. Atomically swaps the in-memory policy engine with the fresh bundle.
4. Serves `/api/v1/decisions/check` locally — identical API surface to the central backend.
5. Streams decision telemetry back to the central API in 5-second batches so the audit log remains the single source of truth.

Latency: central API p95 ≈ 8ms; sidecar p95 < 1ms.

### Policy-as-Code CLI

`scripts/kynara-cli.py` — a stdlib-only Python script (no pip install required) for managing policies through git:

| Subcommand | Description |
|---|---|
| `pull` | Download the live bundle for the org to a JSON file |
| `push` | Upload a bundle file; shows diff, applies with `--force` |
| `diff` | Compute the diff vs. live without applying |
| `verify` | Recompute the bundle checksum and confirm it matches |

Designed for GitOps workflows: commit the bundle to git, run `diff` in CI on every PR, `push` on merge to main.

### CI / CD

`.github/workflows/ci.yml` runs on every push to `main` and every PR:

| Job | Steps |
|---|---|
| `backend` | ruff lint, ruff format, mypy, bandit, alembic migrate, pytest |
| `frontend` | npm ci, tsc, Vite build |
| `e2e` | Playwright against a full docker-compose stack (auth, policy lifecycle) |
| `container` | Docker build + cosign signing + push to GHCR |

### Terraform

`deploy/terraform/` — infrastructure-as-code for AWS:

- ECS Fargate module (backend + frontend as tasks, RDS Postgres, ElastiCache Redis, ALB).
- EKS module (alternative for orgs already on Kubernetes).
- Secrets Manager integration for `JWT_SECRET`, `DATABASE_URL`, `STRIPE_SECRET_KEY`.

### Trust Center

`trust-center/` — a static HTML page hosted at `/trust`:

- Compliance evidence cards (SOC 2, ISO 27001, GDPR, HIPAA, Pen Test).
- Service status link.
- `/.well-known/security.txt` with PGP-signed responsible disclosure policy.

## Request lifecycle: a decision check

```
Agent runtime (Python, TypeScript, AutoGen, CrewAI, OpenAI, Anthropic...)
  │
  │  SDK wraps tool call (decorator / guarded() / callback handler)
  ▼
  kynara.check(subject, action, resource, context)
  │
  │  Option A: HTTPS + API key → Central API
  │  Option B: HTTP → Go Sidecar (local, sub-ms) → batches back to Central API
  ▼
FastAPI → /api/v1/decisions/check
  │
  │  1. Principal resolved from JWT or API key
  │  2. Rate limits applied
  │  3. Redis cache lookup (skip for non-allow effects)
  ▼
PolicyService.decide()
  │
  │  4. Hard gates: agent enabled? org match? plan quota not exceeded?
  │  5. JIT grant check: is there an active time-bound grant that widens scope?
  │  6. Load policies for org (cached 10s)
  │  7. Apply RBAC intersection (agent role ∩ user role)
  │  8. Evaluate policies in priority order
  │  9. Record audit event (hash-chained)
  ▼
Decision returned
  │
  │  effect, matched_policy_id, reason, ttl_seconds, approval_url?
  ▼
SDK
  │
  │  cache allow for ttl_seconds
  │  raise on deny / require_approval
  ▼
Agent continues or aborts
```

## JIT Grant lifecycle

```
Human operator
  │ POST /api/v1/jit-grants { scope, duration_minutes, justification, ticket_url }
  ▼
JIT Grant created (recorded in audit chain)
  │
  │  PolicyService.decide() checks active grants before RBAC intersection
  │  Grant widens effective scopes for its duration
  ▼
Grant expires (auto) or is revoked (admin) → audit event recorded
```

## Policy historical replay

```
Admin proposes a policy change
  │ POST /api/v1/policy-replay { policy, lookback_days }
  ▼
Backend loads ≤ 30 days × 100k audit events with stored DecisionContext
  │
  │  Re-evaluates each event against engine with proposed policy spliced in
  │  Buckets deltas: allow→deny, allow→require_approval, deny→allow, etc.
  ▼
Returns flip counts and affected decision IDs before any change is deployed
```

## Why hash-chained audit vs. immutable storage

An immutable storage backend (S3 Object Lock, QLDB, specialized WORM) is expensive and opaque. A hash chain gives customers a portable integrity proof that can be verified offline with a forty-line script. We chose the chain because:

- Verification is cheap and customer-runnable — no vendor lock-in.
- Integrity is independent of any single storage medium; we can migrate storage without breaking the proof.
- Broken-chain detection is local — we alert on chain gaps the same quarter a PostgreSQL upgrade corrupts a page, not a year later at audit time.

The append-only trigger gives defense in depth: a DBA with production credentials still cannot silently rewrite a row without leaving a gap, and the cron-driven verifier catches gaps within 24 hours.

## Why fail-closed is non-negotiable

If the policy engine is down and agents continue to execute, the security posture of the organization is whatever the most lenient default is. We set that default to `deny` so that outages degrade usefulness, not safety. Customers who need availability over strict correctness can opt into "shadow mode" at decision time, but shadow mode emits `audit.shadow_allow` events so it is visible in reports.

## Plan enforcement

Every API request that touches the decision engine or member management checks the org's active plan entitlements:

- **Seat limit**: `GET /api/v1/org/members` is rate-limited per seat count; invite endpoint rejects over-limit invitations.
- **Decision quota**: the decision endpoint increments a rolling 30-day counter per org. When the quota is reached, decisions return `deny` with `reason: "quota_exceeded"` until the billing cycle rolls over or the plan is upgraded.
- **Trial period**: trial orgs have a hard expiry date. After expiry, write operations (policy changes, agent creation) are blocked; read access and audit export remain available to facilitate offboarding.

## Superadmin

A `superadmin_users` table flags specific user accounts as platform administrators. Superadmins can:

- List and create all organizations.
- Invite members to any organization regardless of their own membership.
- View platform-wide usage metrics.

Superadmin actions are recorded with `event_type=admin.superadmin.*` in the audit chain.

## Scaling notes

- The decision endpoint is stateless and horizontally scales. The in-process client cache is the first line of throughput defense.
- For extreme throughput, run the Go sidecar. It pulls the active JWS-signed policy bundle every 30s and evaluates locally, streaming decision telemetry back. Latency drops from single-digit ms to sub-millisecond at the cost of slightly stale bundles.
- Audit writes are the primary bottleneck. Writes are batched into 5ms windows; a single Postgres writer handles ~20k events/sec on commodity hardware. At higher rates we shard by `org_id` and reconcile chain tips cross-shard.

## Deployment

Everything ships as container images. A reference `docker-compose.yml` in the repo root brings up Postgres, Redis, backend, frontend, and an OTLP collector in under a minute. Production deployments are Terraform-managed on AWS ECS Fargate or EKS — both are supported under `deploy/terraform/`.

## Related docs

- `/docs/api/openapi.yaml` — API reference (30+ paths).
- `/docs/api/integration-guide.md` — how to wire the SDK into an agent; multi-framework examples.
- `/docs/security/threat-model.md` — STRIDE.
- `/docs/security/pentest-plan.md` — annual pen-test scope.
- `/docs/compliance/soc2-control-mapping.md` — SOC 2 TSC map.
- `/docs/compliance/iso27001-soa.md` — ISO 27001 SoA.
- `/docs/compliance/gdpr-dpa.md` — Processor DPA template.
- `/docs/compliance/hipaa-baa.md` — Business Associate Agreement.
- `/docs/compliance/dpia.md` — Data Protection Impact Assessment.
- `/docs/runbooks/incident-response.md` — IR playbook.
- `/trust-center/index.html` — customer-facing compliance evidence page.
- `/scripts/kynara-cli.py` — policy-as-code CLI.
- `/scripts/verify_chain_offline.py` — standalone offline audit chain verifier.
