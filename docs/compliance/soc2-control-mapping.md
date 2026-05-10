# SOC 2 Type II Control Mapping — Kynara

**Report period**: 2026-01-01 through 2026-12-31
**Trust Service Criteria**: Security (CC), Availability (A), Confidentiality (C), Processing Integrity (PI)
**Auditor of record**: [to be named]

This document maps Kynara's control environment to the 2017 Trust Services Criteria. Every control references an implementation artifact — a code path, configuration file, or operational runbook — that an auditor can sample against.

## 1. Control environment (CC1)

| # | Criterion | Kynara control | Evidence |
|---|---|---|---|
| CC1.1 | Demonstrates commitment to integrity and ethical values | Annual code of conduct acknowledgment; documented ethics escalation path | HR records; `/docs/policies/code-of-conduct.md` |
| CC1.2 | Board oversight of internal control | Quarterly security steering committee; minutes archived | Confluence `SEC/Minutes` |
| CC1.3 | Establishes structures, reporting lines, and authorities | RACI matrix for security incidents; delegation-of-authority policy | `/docs/org/raci.md` |
| CC1.4 | Demonstrates commitment to competence | Mandatory annual security training (≥90% completion); role-based training for engineers | LMS records |
| CC1.5 | Enforces accountability | Performance reviews include security objectives; quarterly access reviews | HRIS exports |

## 2. Communication and information (CC2)

| # | Criterion | Control | Evidence |
|---|---|---|---|
| CC2.1 | Obtains or generates relevant quality information | Logs aggregated in central SIEM (OpenTelemetry → Prometheus → Grafana) | `/backend/app/core/telemetry.py` |
| CC2.2 | Internal communication of information | Weekly security bulletin; quarterly all-hands security review | Email archives |
| CC2.3 | External communication | Security page publishes status, advisories, and Trust Center | `trust.kynara.example.com` |

## 3. Risk assessment (CC3)

Kynara maintains a risk register in Jira (`SEC-RISK`). Each risk carries: likelihood (1–5), impact (1–5), owner, treatment (accept / mitigate / transfer / avoid), and a due date. The register is reviewed by the security steering committee quarterly.

| # | Criterion | Control |
|---|---|---|
| CC3.1 | Specifies objectives to enable risk identification | Published security objectives: confidentiality of policy data, integrity of audit log, availability ≥ 99.9% |
| CC3.2 | Identifies and assesses risks | Threat model (`/docs/security/threat-model.md`); annual third-party pen test |
| CC3.3 | Fraud risk consideration | Dual control required for production database changes; audit log tamper-evidence |
| CC3.4 | Change assessment | Risk review step in the release process for any change touching auth, audit, or policy engine |

## 4. Monitoring activities (CC4)

| # | Criterion | Control | Evidence |
|---|---|---|---|
| CC4.1 | Selects, develops, and performs evaluations | Continuous control monitoring via Drata; weekly anomaly review | Drata screenshots |
| CC4.2 | Evaluates and communicates deficiencies | JIRA `SEC` project; SLO-based alert routing | Jira exports |

## 5. Control activities (CC5)

| # | Criterion | Control |
|---|---|---|
| CC5.1 | Selects and develops control activities | Control matrix maintained in this document |
| CC5.2 | Selects and develops general controls over technology | See CC6–CC8 below |
| CC5.3 | Deploys controls through policies and procedures | Policies version-controlled in `/docs/policies`; changes require approval |

## 6. Logical and physical access controls (CC6)

### CC6.1 — Restricts logical access

Control: Access to production systems is gated by SSO (Okta) with SAML 2.0 + OIDC, enforced by corporate device certificates. No standing access; engineers request time-boxed grants via a break-glass workflow.

Implementation:

- `backend/app/auth/` implements Argon2id password hashing (peppered), JWT issuance, rotating refresh tokens with reuse detection.
- `backend/app/sso/okta_oidc.py` uses PKCE S256 and JWKS verification.
- `backend/app/sso/saml.py` requires signed AuthnRequests and signed assertions.
- Row-Level Security (PostgreSQL) enforces org isolation at the database layer — see migration `20260101_0001_initial_schema`.

### CC6.2 — Authorizes new access and modifies existing access

Access requests flow through an internal portal that records: requester, approver, scope, justification, duration. Approvals generate audit events recorded in Kynara itself (self-hosting our control).

### CC6.3 — Removes access

Offboarding triggers automated deprovisioning: SCIM push from HRIS deactivates the user within 5 minutes of role change.

### CC6.6 — Logical access security measures

| Measure | Implementation |
|---|---|
| Password strength | Argon2id, min 12 chars; breach-list check via k-anonymity API |
| MFA | Required for all non-SSO users; TOTP or WebAuthn |
| Session timeout | 15 min access token; 30 day rotating refresh; forced re-auth on role change |
| Rate limiting | slowapi middleware: 100 RPS per principal, 1,000 RPS per org for decisions |

### CC6.7 — Restricts movement of information

TLS 1.3 required on all ingress and egress. Database connections use certificate-pinned TLS. Outbound from workers is egress-filtered by IP allowlist.

### CC6.8 — Prevents, detects, and acts on unauthorized software

EDR (CrowdStrike) on all developer workstations and servers. Container images are Cosign-signed and admission-controlled by Kyverno.

## 7. System operations (CC7)

### CC7.1 — Detects and monitors system component changes

All infrastructure changes via Terraform in `infra/`. PRs require two approvals; Atlantis plans posted for review.

### CC7.2 — Monitors for anomalies

Falco runtime security on hosts. Prometheus alert rules for: auth_failures_ratio, decision_deny_spike, audit_chain_broken, api_5xx_ratio.

### CC7.3 — Evaluates security events

On-call rotation (PagerDuty) with documented runbooks. Mean time to acknowledge: 5 min; mean time to mitigate target: 60 min for Sev-1.

### CC7.4 — Responds to security incidents

IR playbook at `/docs/runbooks/incident-response.md`. Post-incident review within 5 business days for any Sev-1 or Sev-2.

### CC7.5 — Recovery

RPO: 15 minutes (WAL archiving to object storage). RTO: 4 hours. Quarterly DR drills recover to a cold region; results logged.

## 8. Change management (CC8)

### CC8.1 — Authorizes, designs, develops, configures, documents, tests, approves, and implements changes

- Every code change goes through pull request review with at least one peer approver.
- CI runs: unit tests, integration tests (real Postgres), static analysis (ruff, mypy, bandit), SBOM generation, container scanning (Trivy), SAST (Semgrep).
- Deploys are blue/green via Argo Rollouts with automated rollback on SLO regression.
- Database migrations use Alembic; destructive migrations require DBA approval tag.

## 9. Risk mitigation (CC9)

Vendor risk: Each third-party processor is reviewed against an intake questionnaire; high-risk vendors receive annual re-assessment. Current subprocessor list:

| Vendor | Function | Region | DPA signed |
|---|---|---|---|
| Amazon Web Services | Infrastructure hosting | us-east-1, eu-west-1 | Yes |
| Stripe | Payment processing | US + EU | Yes |
| Okta | Identity provider | US | Yes |
| Datadog | Observability | US | Yes |

## 10. Availability (A)

| # | Criterion | Control |
|---|---|---|
| A1.1 | Maintains capacity to meet commitments | Auto-scaling on CPU and decision queue depth; load tests at 2× peak |
| A1.2 | Authorizes, designs, develops environmental protections | Multi-AZ deployment; WAL archival to object storage |
| A1.3 | Tests recovery | Quarterly DR drill; tabletop exercises twice yearly |

## 11. Confidentiality (C)

| # | Criterion | Control |
|---|---|---|
| C1.1 | Identifies and maintains confidential information | Data classification policy; `classification` attribute on every resource object |
| C1.2 | Disposes of confidential information | Soft-delete with 30-day cryptoshred; audit log retained 7 years then cryptoshredded |

Customer data is encrypted at rest (AES-256, AWS KMS with customer-managed keys available on Enterprise) and in transit (TLS 1.3). Policy data and audit logs are encrypted with per-tenant data keys.

## 12. Processing integrity (PI)

| # | Criterion | Control |
|---|---|---|
| PI1.1 | Obtains or generates accurate input | Request schemas validated with Pydantic; rejected input returns 400 with request_id |
| PI1.2 | Processes inputs completely and accurately | Transactional writes with Postgres; idempotency keys on billing and decision endpoints |
| PI1.3 | Generates complete and accurate output | Audit log hash-chain provides tamper evidence; `/api/v1/audit/verify` recomputes the chain end-to-end |
| PI1.4 | Stores completely and accurately | Checksums on object storage; monthly reconciliation of billing usage vs. Stripe |
| PI1.5 | Processes inputs within reasonable time | SLOs: p99 decisions under 15ms, p99.9 under 40ms |

## 13. Audit log integrity — a detailed example

Every decision writes a row to `audit_events`:

```
id, sequence, ts, event_type, actor, resource_type, resource_id,
outcome, payload, prev_hash, entry_hash
```

The `entry_hash` is computed as:

```
SHA256(prev_hash || sequence || ts || event_type || actor ||
       canonical_json(payload))
```

An append-only Postgres trigger refuses UPDATE/DELETE on this table. `POST /api/v1/audit/verify` walks the chain and returns `broken_at` if any `entry_hash` fails recomputation. This control addresses PI1.3, CC7.2 (anomaly detection on chain-broken events), and CC3.3 (fraud risk).

## 14. Summary statement

Management asserts that the controls described above were suitably designed and operating effectively throughout the report period to provide reasonable assurance that Kynara's service commitments and system requirements were achieved, based on the applicable Trust Services Criteria.
