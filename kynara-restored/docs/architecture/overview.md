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

A single-page app under `/frontend`. Authenticates humans via password or SSO, lets them browse agents, tools, policies, audit events, and billing, and provides an ABAC condition editor with a live simulator.

### Backend (FastAPI + async SQLAlchemy)

Under `/backend/app`. Async Python 3.12. Key packages:

- `auth` — password hashing (Argon2id + pepper), JWT + rotating refresh, session model.
- `sso` — Okta OIDC (PKCE) and SAML 2.0 SP via `python3-saml`.
- `policy` — pure policy engine (`engine.py`) and a service wrapper (`service.py`) that applies hard gates (disabled agent, org mismatch), RBAC intersection, and the ABAC condition tree.
- `audit` — hash-chained writes and a verification endpoint.
- `billing` — Stripe usage metering, checkout, and webhook verification.
- `middleware` — security headers, request context, body-size limits, slowapi rate limits.
- `api/v1` — versioned REST endpoints.

### Database (PostgreSQL 15+)

Multi-tenant. Every tenant-scoped table carries `org_id` and has a Row-Level Security policy that requires `current_setting('app.org_id')` to match. Sessions opened by the application set the GUC on first use; background jobs use a special service identity.

The `audit_events` table is append-only by trigger — attempted `UPDATE` or `DELETE` raises `P0001`.

### Cache (Redis)

Short-lived decision cache (default 5s TTL). `require_approval` and `deny` decisions are never cached.

### Agent SDK (Python)

Under `/sdk`. Provides:

- `Kynara(...)` client with retries and in-process cache.
- `@permission_required(...)` decorator.
- `KynaraCallbackHandler` for LangChain `on_tool_start`.
- Context-managed guards and typed errors (`PermissionDenied`, `ApprovalRequired`, `KynaraUnavailable`).

### Observability

OpenTelemetry traces (OTLP), Prometheus metrics, and structlog JSON logs. ContextVars propagate `request_id`, `org_id`, `user_id`, `trace_id` to every log line.

## Request lifecycle: a decision check

```
Agent runtime
  │
  │  SDK wraps tool call
  ▼
  kynara.check(subject, action, resource, context)
  │
  │  HTTPS + API key
  ▼
FastAPI → /api/v1/decisions/check
  │
  │  1. Principal resolved from API key
  │  2. Rate limits applied
  │  3. Redis cache lookup (skip for non-allow effects)
  ▼
PolicyService.decide()
  │
  │  4. Hard gates: agent enabled? org match?
  │  5. Load policies for org (cached 10s)
  │  6. Apply RBAC intersection
  │  7. Evaluate policies in priority order
  │  8. Record audit event (hash-chained)
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

## Why hash-chained audit vs. immutable storage

An immutable storage backend (S3 Object Lock, QLDB, specialized WORM) is expensive and opaque. A hash chain gives customers a portable integrity proof that can be verified offline with a forty-line script. We chose the chain because:

- Verification is cheap and customer-runnable — no vendor lock-in.
- Integrity is independent of any single storage medium; we can migrate storage without breaking the proof.
- Broken-chain detection is local — we alert on chain gaps the same quarter a PostgreSQL upgrade corrupts a page, not a year later at audit time.

The append-only trigger gives defense in depth: a DBA with production credentials still cannot silently rewrite a row without leaving a gap, and the cron-driven verifier catches gaps within 24 hours.

## Why fail-closed is non-negotiable

If the policy engine is down and agents continue to execute, the security posture of the organization is whatever the most lenient default is. We set that default to `deny` so that outages degrade usefulness, not safety. Customers who need availability over strict correctness can opt into a "shadow mode" at decision time, but shadow mode emits `audit.shadow_allow` events so it is visible in reports.

## Scaling notes

- The decision endpoint is stateless and horizontally scales. The in-process client cache is the first line of throughput defense.
- For extreme throughput, run the sidecar. It pulls the active policy bundle every 30s and evaluates locally, streaming decision telemetry back. Latency drops from single-digit ms to sub-millisecond at the cost of slightly stale bundles.
- Audit writes are the primary bottleneck. Writes are batched into 5ms windows; a single Postgres writer handles ~20k events/sec on commodity hardware. At higher rates we shard by `org_id` and reconcile chain tips cross-shard.

## Deployment

Everything ships as container images. A reference `docker-compose.yml` in the repo root brings up Postgres, Redis, backend, frontend, and an OTLP collector in under a minute. Production deployments are Terraform-managed on AWS ECS Fargate or EKS — both are supported.

## Related docs

- `/docs/api/openapi.yaml` — API reference.
- `/docs/api/integration-guide.md` — how to wire the SDK into an agent.
- `/docs/security/threat-model.md` — STRIDE.
- `/docs/security/pentest-plan.md` — annual pen-test scope.
- `/docs/compliance/soc2-control-mapping.md` — SOC 2 TSC map.
- `/docs/compliance/iso27001-soa.md` — ISO 27001 SoA.
- `/docs/compliance/gdpr-dpa.md` — Processor DPA template.
- `/docs/compliance/hipaa-baa.md` — Business Associate Agreement.
- `/docs/compliance/dpia.md` — Data Protection Impact Assessment.
- `/docs/runbooks/incident-response.md` — IR playbook.
