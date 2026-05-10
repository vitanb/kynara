# Kynara — Enterprise AI Agent Permission System

Kynara is a control plane and runtime enforcement layer for AI agents. It answers the
question **"is this agent allowed to do this, right now, on behalf of this user?"** and
produces a tamper-evident audit trail of every decision.

## What's in this repo

```
.
├── backend/          FastAPI control plane: auth, policy engine, audit, billing, SSO, APIs
├── frontend/         React + Vite admin UI (dashboard, policy editor, audit viewer, billing)
├── sdk/              Python SDK — decorator/context-manager runtime enforcement for agents
├── docs/             Architecture, API reference, compliance (SOC 2 / ISO 27001 / GDPR / HIPAA)
├── security/         Threat model, pen-test plan, security audit report
├── demo/             Self-contained interactive HTML demo of the whole product
├── scripts/          Developer helpers, seed data
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
# Default login: admin@demo.kynara.dev / kynara-demo

# 4. Install the runtime SDK in your agent
pip install -e sdk/
```

Then wrap your agent's tool calls:

```python
from kynara_sdk import Kynara, permission_required

kynara = Kynara(api_key="sk_live_...", base_url="https://api.kynara.dev")

@permission_required("crm.contacts.read", resource_arg="contact_id")
def read_contact(contact_id: str):
    return crm.get(contact_id)
```

If the agent lacks permission, the call raises `PermissionDenied` before any side-effects
occur, and the attempt is recorded in the audit log.

## Core concepts

- **Subject** — the acting principal. Usually `agent:<id>` acting `on_behalf_of user:<id>`.
- **Action** — a namespaced verb like `crm.contacts.read` or `payments.refund.issue`.
- **Resource** — the target of the action, with attributes (owner, classification, region).
- **Policy** — a rule `(subject, action, resource, context) → allow | deny | require_approval`.
- **Decision** — the audited, hash-chained output of the policy engine for one check.

The data model is RBAC + ABAC: roles grant capabilities, and conditions on attributes
(time of day, data classification, IP, approval state) gate the final decision.

## What "real" means here

| Claim                            | What's in this repo                                              |
|----------------------------------|------------------------------------------------------------------|
| Real auth                        | Argon2id password hashing, JWT access + rotating refresh tokens, API keys with per-key scopes + rate limits |
| Real DB                          | Postgres, SQLAlchemy 2.x, Alembic migrations, row-level multi-tenancy |
| Real runtime enforcement         | Python SDK with decorator + middleware + context manager; decisions cached and streamed to audit |
| Real SSO                         | Okta SAML 2.0 + OIDC flows, SCIM 2.0 user provisioning stubs     |
| Real billing                     | Stripe customer/subscription/usage metering, invoice webhooks    |
| Security audit                   | Hash-chained (Merkle) audit log, integrity verification job      |
| Monitoring                       | Structured JSON logs, OpenTelemetry traces + metrics, Prometheus exporter |
| Pen-test                         | OWASP ASVS + OWASP LLM Top 10 checklist, runnable script harness |
| APIs                             | OpenAPI 3.1 spec, versioned under `/api/v1`                      |
| Compliance                       | SOC 2 Type II control mapping, ISO 27001 Annex A mapping, GDPR DPA template, HIPAA overview, DPIA |

## Licensing

Source-available under the Business Source License 1.1. See `LICENSE`.
