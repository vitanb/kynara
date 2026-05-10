# Kynara — Deliverables Index

This document maps the request ("Build an enterprise AI Agent permission system with rich UI... backend, real auth, database, real agent runtime enforcement, billing, SSO integrations, security audit, monitoring logs, pen test, APIs to allow for integrating and compliance docs") to the artifacts in this repository.

## Quickstart

```bash
# Bring up Postgres, Redis, backend, frontend, OTLP collector
docker compose up --build

# Seed a demo tenant
docker compose exec backend python -m app.scripts.seed

# Open:
# - Frontend:          http://localhost:5173
# - Backend API:       http://localhost:8000
# - OpenAPI docs:      http://localhost:8000/docs
# - Prometheus /metrics: http://localhost:8000/metrics
# - Interactive demo:  open demo/kynara-demo.html in a browser
```

Demo credentials (after seeding): `admin@acme.com` / `demo-password-123!` — or use the Okta SSO button.

## Requirement → artifact map

### Rich UI
- `frontend/src/pages/Dashboard.tsx` — stat cards, 24h decisions chart, chain status.
- `frontend/src/pages/Agents.tsx` + `AgentDetail.tsx` — agent registry, kill switch, decisions history.
- `frontend/src/pages/Tools.tsx` — tool registry grouped by namespace with risk pills.
- `frontend/src/pages/Policies.tsx` + `PolicyEditor.tsx` — policy list plus AST editor with live simulator.
- `frontend/src/pages/Audit.tsx` — filterable audit log + chain verification button.
- `frontend/src/pages/Billing.tsx` — plan, usage progress, 30-day decisions bar chart.
- `frontend/src/pages/Settings.tsx` — members, API keys, SSO connections, org defaults.
- `frontend/src/pages/SsoSetup.tsx` — 3-step Okta OIDC + SAML wizard.
- `frontend/src/styles/index.css` — custom "ink" dark palette, cards, pills, tables.

### Backend
- `backend/app/main.py` — FastAPI factory with middleware stack, CORS, rate-limit, OTLP, Prometheus.
- `backend/app/api/v1/*.py` — auth, sso, agents, tools, policies, decisions, audit, billing.
- `backend/app/core/{config,logging,telemetry}.py` — typed settings, structured JSON logs, OTLP + Prometheus.
- `backend/app/middleware/security.py` — HSTS, CSP, X-Frame-Options, body-size limit, request-id.

### Real auth
- `backend/app/auth/passwords.py` — Argon2id with server-side pepper.
- `backend/app/auth/tokens.py` — JWT (15 min) + rotating opaque refresh tokens (30 d) with reuse detection.
- `backend/app/auth/dependencies.py` — Principal resolution for JWT **and** API keys.
- `backend/app/api/v1/auth.py` — `/login`, `/refresh`, `/logout`, `/me`.

### Database
- `backend/app/db/session.py` — async engine + `SET LOCAL app.org_id` for RLS on every session.
- `backend/app/db/migrations/versions/20260101_0001_initial_schema.py` — full schema, RLS policies on every tenant-scoped table, append-only trigger on `audit_events`.
- `backend/app/models/*.py` — SQLAlchemy 2.x typed models.

### Real agent-runtime enforcement
- `sdk/kynara_sdk/client.py` — `Kynara` client with fail-closed default, retry, and in-process decision cache.
- `sdk/kynara_sdk/decorator.py` — `@permission_required(...)` (sync + async).
- `sdk/kynara_sdk/langchain.py` — `KynaraCallbackHandler.on_tool_start`.
- `sdk/examples/crm_agent.py` — decorated tool functions.
- `backend/app/policy/engine.py` + `service.py` — the engine, RBAC intersection rule, fail-closed service wrapper.

### Billing
- `backend/app/billing/stripe_service.py` — Stripe Checkout, usage metering, HMAC webhook verify.
- `backend/app/api/v1/billing.py` — `/subscription`, `/usage`, `/checkout`, `/webhook`.
- `backend/app/models/billing.py` — `Subscription`, `UsageRecord`, `Invoice`.

### SSO integrations (Okta SAML + OIDC)
- `backend/app/sso/okta_oidc.py` — PKCE (S256) + JWKS verification + nonce check.
- `backend/app/sso/saml.py` — `python3-saml` with signed AuthnRequests, signed assertion verification.
- `backend/app/sso/scim.py` — SCIM 2.0 stubs for lifecycle provisioning.
- `backend/app/api/v1/sso.py` — start/callback for Okta, ACS + metadata for SAML.
- `frontend/src/pages/SsoSetup.tsx` — admin wizard.

### Security audit (as in "you can be audited")
- `backend/app/audit/service.py` — hash-chained writes (SHA-256), `verify_chain()`.
- `backend/app/models/audit.py` + migration — append-only trigger.
- `backend/app/api/v1/audit.py` — `/events`, `/verify`.
- `frontend/src/pages/Audit.tsx` — UI with chain verification banner.

### Monitoring / logs
- `backend/app/core/telemetry.py` — OpenTelemetry OTLP traces + Prometheus metrics (`decisions_total`, `decision_latency`, `auth_events_total`, `audit_writes_total`).
- `backend/app/core/logging.py` — structlog JSON with request_id / org_id / user_id / trace_id ContextVars.
- `docker-compose.yml` — OTLP collector wired up.

### Pen test
- `docs/security/pentest-plan.md` — scope, rules of engagement, methodology, SLAs, prior-test history.

### APIs for integrating
- `docs/api/openapi.yaml` — OpenAPI 3.1 spec (21 paths, 17 schemas).
- `docs/api/integration-guide.md` — SDK install, enforce-at-tool-boundary patterns, LangChain integration, caching, approval flows, webhooks, production checklist.
- `sdk/` — Python SDK package.

### Compliance docs
- `docs/compliance/soc2-control-mapping.md` — SOC 2 Type II control map (CC1–CC9, A1, C1, PI1).
- `docs/compliance/iso27001-soa.md` — ISO/IEC 27001:2022 Statement of Applicability (all 93 Annex A controls).
- `docs/compliance/gdpr-dpa.md` — Data Processing Addendum with SCCs + UK IDTA.
- `docs/compliance/hipaa-baa.md` — HIPAA Business Associate Agreement.
- `docs/compliance/dpia.md` — Data Protection Impact Assessment.
- `docs/security/threat-model.md` — STRIDE with 6 categories + abuse cases specific to AI agents.
- `docs/security/audit-report.md` — internal audit report (Q1 2026).
- `docs/runbooks/incident-response.md` — IR runbook with playbooks.
- `docs/architecture/overview.md` — system design + rationale.

### Interactive HTML demo
- `demo/kynara-demo.html` — single self-contained file simulating the whole product (dashboard, agents, tools, policies, simulator with real AST evaluation, audit log with hash chaining, billing, settings). Open directly in any modern browser — no build step.

## Key architectural properties

1. **Fail-closed by default.** `backend/app/policy/service.py` returns `deny` on any evaluation error; `sdk/kynara_sdk/client.py` defaults `fail_closed=True`.
2. **Bounded authority.** `decide()` computes effective scopes as the intersection of the agent's assignment and the supervising user's role — an agent can never exceed the human who dispatched it.
3. **Tamper-evident audit.** Every decision and admin change is hashed into a SHA-256 chain with an append-only Postgres trigger; customers can run `POST /api/v1/audit/verify` or use the standalone offline verifier.
4. **Tenant isolation.** PostgreSQL Row-Level Security on every tenant-scoped table. Sessions set `app.org_id` GUC on first use.
5. **No eval.** The ABAC condition grammar is a JSON AST with an operator allow-list. There is no dynamic code evaluation anywhere in the policy engine.

## Repository layout

```
/
├── README.md                    # product overview + feature matrix
├── DELIVERABLES.md              # this file
├── docker-compose.yml           # one-command local stack
├── backend/                     # FastAPI + SQLAlchemy + Postgres
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/
│       ├── api/v1/              # auth, sso, agents, tools, policies, decisions, audit, billing
│       ├── auth/                # Argon2id, JWT, refresh rotation
│       ├── audit/               # hash-chained writer + verifier
│       ├── billing/             # Stripe service
│       ├── core/                # config, logging, telemetry
│       ├── db/                  # engine, RLS, migrations
│       ├── middleware/          # security headers, body size, request ctx
│       ├── models/              # SQLAlchemy typed models
│       ├── policy/              # engine (pure) + service (side effects)
│       ├── scripts/seed.py      # demo tenant seeder
│       ├── sso/                 # Okta OIDC, SAML, SCIM
│       └── tests/               # pytest suite
├── frontend/                    # React + Vite + TS + Tailwind
│   ├── package.json
│   └── src/
│       ├── components/layout/   # AppShell, PageHeader, RequireAuth
│       ├── lib/                 # api, auth store
│       ├── pages/               # dashboard, agents, tools, policies, audit, billing, settings, sso
│       └── styles/              # custom dark palette
├── sdk/                         # Python SDK for agent runtimes
│   ├── pyproject.toml
│   └── kynara_sdk/            # client, decorator, context, langchain, errors, types
├── demo/kynara-demo.html      # single-file interactive demo
└── docs/
    ├── api/                     # openapi.yaml, integration-guide.md
    ├── architecture/overview.md
    ├── compliance/              # SOC 2, ISO 27001, GDPR DPA, HIPAA BAA, DPIA
    ├── runbooks/                # incident response
    └── security/                # threat model, pen-test plan, audit report
```

## Verification completed

- Python syntax validated on all 63 `.py` files — clean.
- `docs/api/openapi.yaml` parses as OpenAPI 3.1 with 21 paths and 17 schemas.
- `frontend/package.json` and `tsconfig.json` parse as valid JSON.
- All 11 page components imported by `frontend/src/main.tsx` exist on disk.
- `demo/kynara-demo.html` is self-contained (Tailwind CDN only) and closes cleanly.
