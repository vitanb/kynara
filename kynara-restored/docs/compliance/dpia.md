# Data Protection Impact Assessment (DPIA) — Kynara

**Version**: 1.0
**Date**: 2026-04-21
**DPO of record**: dpo@kynara.example.com
**Project**: Kynara AI Agent Permission System
**Scope of this DPIA**: Processing of Personal Data in the context of authenticating users, evaluating authorization decisions for AI agents, and maintaining audit logs.

This DPIA is prepared pursuant to Article 35 GDPR. It is reviewed whenever a material change is made to the service, and at least every 24 months.

## 1. Describe the Processing

### 1.1 Nature
Kynara acts as a Processor on behalf of Customer (Controller). The service:

- authenticates human users via password + MFA, SAML 2.0, or OIDC;
- registers AI agents and their capabilities;
- evaluates per-action policy checks that combine RBAC and ABAC over a JSON AST condition grammar;
- writes every decision to a tamper-evident, hash-chained audit log.

### 1.2 Scope
- **Categories of data subjects**: Customer's employees, contractors, and, where Customer chooses to pass user data, Customer's end users.
- **Categories of Personal Data**: identifiers (email, user ID, IP, device), authentication data (password hashes, MFA state, SSO attributes), and any data Customer includes in the `resource.attrs` or `context` fields of DecisionRequests.
- **Duration**: for the life of the Customer's subscription, plus up to seven years for audit records (encrypted, then cryptoshredded).
- **Geographies**: Primary processing in AWS `us-east-1` or `eu-west-1` depending on Customer selection; backups cross-region within the same regulatory area.

### 1.3 Context
Customers range from small teams piloting AI agents to Fortune-500 deployments. Data subjects may or may not have a direct relationship with Kynara; in most cases their relationship is with Customer.

### 1.4 Purposes
- Enforce authorization policies so AI agents cannot exceed authority granted to the supervising human.
- Provide auditability to meet customer obligations under SOC 2, ISO 27001, HIPAA, GDPR Article 22, and internal AI-governance policies.
- Provide usage metering for billing.

## 2. Assess necessity and proportionality

### 2.1 Lawful basis
Primary lawful basis is Article 6(1)(f) legitimate interests (operating the service), supported by Customer's contractual necessity (6(1)(b)) between Customer and its data subjects. Where Customer is itself a Processor, its Controller bears the primary lawful-basis responsibility.

### 2.2 Purpose limitation
Data is Processed only to provide the service. Kynara does not train AI models on Customer Personal Data and does not enrich Personal Data with third-party datasets.

### 2.3 Data minimization
- DecisionRequest payloads are validated against a strict schema; unrecognized fields are rejected rather than silently stored.
- Developers are directed in the integration guide to pass stable IDs instead of direct identifiers wherever possible.
- Request bodies are truncated in application logs after 2 KB; PII patterns are redacted by the log pipeline.

### 2.4 Accuracy
Customers can rectify user records via the Settings UI or the Management API; changes propagate to Kynara within 60 seconds.

### 2.5 Storage limitation
Operational records: retained for the life of the subscription. Audit log: cryptoshredded at 7 years unless customer configures a shorter period.

### 2.6 Rights of data subjects
Self-service export and deletion endpoints implement Articles 15, 16, 17, and 20. For Article 22 (automated individual decision-making), every policy decision is recorded with the matched policy, the condition evaluation trace, and a human-readable reason, enabling the Customer to provide "meaningful information about the logic involved."

## 3. Consultation

The DPO consulted the following stakeholders:

- Engineering leadership (CTO, Principal Engineer, Security)
- Legal (General Counsel, Privacy Counsel)
- Customer Advisory Council (two Fortune-100 customer CISOs)
- External counsel specializing in AI governance

## 4. Risk identification and assessment

Risks are scored as Likelihood × Severity on a 1–5 scale.

| # | Risk | L | S | Inherent | Mitigations | Residual |
|---|---|---|---|---|---|---|
| R1 | Unauthorized access to PII by another tenant | 2 | 5 | 10 | Postgres RLS with `app.org_id` GUC; per-tenant data keys; quarterly access reviews | 2 |
| R2 | Compromise of decision-check API enables impersonation | 2 | 5 | 10 | PKCE OIDC; signed SAML; JWT 15-min TTL; refresh reuse detection invalidates chain | 2 |
| R3 | Audit log tampering hides misuse | 2 | 5 | 10 | Hash chain with SHA-256; append-only trigger; weekly chain-verify cron with alert | 1 |
| R4 | Over-retention beyond stated purpose | 3 | 3 | 9 | Retention jobs cryptoshred at 7 years; customer-configurable shorter windows | 2 |
| R5 | Excessive data in DecisionRequests | 4 | 3 | 12 | Schema validation; log truncation + PII redaction; integration guide warns | 4 |
| R6 | Sub-processor lack of controls | 2 | 4 | 8 | Sub-processor due diligence; DPAs; annual reassessment | 2 |
| R7 | International transfer without valid basis | 2 | 5 | 10 | SCCs + TIA on file; EU region option; customer-selectable region | 2 |
| R8 | ML-based bias in suggested policies (future) | 3 | 4 | 12 | Feature gated; decisions require human approval; bias monitoring planned | 6 |
| R9 | Insider misuse of production access | 2 | 5 | 10 | JIT elevation; dual control for DB changes; anomaly detection on admin audit | 2 |
| R10 | Ransomware on operational systems | 2 | 4 | 8 | EDR; immutable containers; 15-min RPO backups in separate account | 2 |

## 5. Measures to reduce risk

The mitigations above are in production or in the 2026 roadmap. Notable items for customer-visible assurance:

- **Hash chain** — Customers can continuously verify the integrity of their audit log via `POST /api/v1/audit/verify`, or subscribe to the `audit.chain_broken` webhook.
- **Region pinning** — Enterprise customers may restrict all processing to `eu-west-1` to address Schrems II concerns. Metadata (timezone of invoices, etc.) is stored in-region.
- **Synthetic data only in non-prod** — Test environments use generated data; production Personal Data is never copied.
- **Automated DPIA re-review** — Drata-integrated workflow re-opens this DPIA when any of the following change: sub-processors, data categories, retention, cross-border transfers, encryption keys.

## 6. Consultation with supervisory authority

No prior consultation with a supervisory authority under Article 36 is required at this time; residual risks are assessed as acceptable. The DPO will reconsider if risks R5 or R8 rise in residual score.

## 7. Sign-off

| Role | Name | Date |
|---|---|---|
| Data Protection Officer | [DPO] | 2026-04-21 |
| Chief Information Security Officer | [CISO] | 2026-04-21 |
| General Counsel | [GC] | 2026-04-21 |
