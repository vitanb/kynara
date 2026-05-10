# Kynara Threat Model (STRIDE)

**Version**: 1.0
**Date**: 2026-04-21
**Owner**: Security Engineering
**Review cadence**: every 6 months, or on material architectural change.

This document models the threats against Kynara using STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege). It complements the SOC 2 control mapping and ISO 27001 SoA by showing how each identified threat is mitigated.

## 1. System description (data flow)

```
                            ┌──────────────────────────┐
   Operator ──── HTTPS ────▶│  Frontend (React SPA)    │
   (browser)                └───────────┬──────────────┘
                                        │ JWT
                           HTTPS / JSON │
                                        ▼
                            ┌──────────────────────────┐
 AI agent runtime ─── API ─▶│  Backend (FastAPI)       │◀── Webhook (Stripe)
 (with SDK)                 │  ┌────────┬────────────┐ │
                            │  │ auth   │ policies   │ │
                            │  │ sso    │ decisions  │ │
                            │  │ audit  │ billing    │ │
                            │  └────────┴────────────┘ │
                            └──────┬─────────┬─────────┘
                                   │         │
                                   ▼         ▼
                         ┌─────────────┐  ┌────────────┐
                         │ PostgreSQL  │  │ Redis      │
                         │ (RLS)       │  │ (cache)    │
                         └──────┬──────┘  └────────────┘
                                │
                                ▼
                        WAL archive to S3
```

## 2. Assets

| ID | Asset | Classification | Impact of compromise |
|---|---|---|---|
| A1 | Customer Personal Data | Confidential | Regulatory, contractual, reputational |
| A2 | Authorization policies | Confidential | Bypassable security controls; breach chain |
| A3 | Audit log | Restricted (integrity) | Undetected misuse; fraud; failed audits |
| A4 | JWT signing secret | Restricted | Total compromise of authentication |
| A5 | Database master credentials | Restricted | Exfiltration of all tenants' data |
| A6 | Stripe API keys | Restricted | Financial fraud, refunds |
| A7 | KMS encryption keys | Restricted | Decrypt at-rest data |
| A8 | Container signing keys | Restricted | Supply-chain attack |

## 3. Trust boundaries

- T1: Public internet ↔ Edge/CDN (Cloudflare) ↔ Load balancer.
- T2: Load balancer ↔ Backend services.
- T3: Backend ↔ Postgres.
- T4: Backend ↔ Redis.
- T5: Backend ↔ External IdPs (Okta/Azure AD), Stripe.
- T6: Operator browser ↔ Frontend.
- T7: Agent runtime ↔ Backend (SDK → /decisions/check).

## 4. Threats and mitigations

### 4.1 Spoofing

| ID | Threat | Boundary | Mitigation | Residual |
|---|---|---|---|---|
| S1 | Attacker forges JWT | T2 | HS256 with server-secret; short TTL; rotation; JWKS for SSO-issued tokens | Low |
| S2 | Session hijacking via XSS | T6 | CSP (default-src 'self'); HttpOnly + Secure + SameSite=Strict refresh cookies; frontend stores access token in sessionStorage only | Low |
| S3 | Stolen API key used from new IP | T7 | Per-key rate limits; IP allowlists per key; anomaly detection on geolocation jumps | Medium |
| S4 | IdP response forgery | T5 | SAML AuthnRequest signing; assertion signature verification against IdP cert; OIDC nonce + state + PKCE S256 | Low |
| S5 | Stripe webhook replay or forgery | T5 | HMAC verification of every webhook with timestamp check (±5 min) | Low |

### 4.2 Tampering

| ID | Threat | Boundary | Mitigation | Residual |
|---|---|---|---|---|
| T1 | Direct DB edit alters a policy | T3 | Dual-control IAM; every DB session writes an admin audit event; policy reads check `policy.checksum` signed by server | Low |
| T2 | Audit log rewritten to hide misuse | T3 | Hash chain with SHA-256 `entry_hash = SHA256(prev_hash ‖ sequence ‖ ts ‖ event_type ‖ actor ‖ canonical_json(payload))`; append-only Postgres trigger; chain verify endpoint | Low |
| T3 | TLS downgrade | T1 | HSTS with preload (1 year); TLS 1.3 only at edge; certificate pinning for internal calls | Low |
| T4 | Request body tampering in transit | T1/T2 | mTLS within VPC; edge WAF inspects content | Low |
| T5 | Supply-chain substitution of a container image | T2 | Cosign signing; Kyverno admission policy verifies signature and attestations | Low |
| T6 | Malicious npm/pypi dependency | Build | Pinned lockfiles; `pip install --require-hashes`; Trivy + Grype in CI | Medium |

### 4.3 Repudiation

| ID | Threat | Boundary | Mitigation | Residual |
|---|---|---|---|---|
| R1 | Admin denies making a policy change | All | Every write to policies/roles/agents writes to `audit_events` with `event_type=admin.*` | Low |
| R2 | Agent denies making a denied request | T7 | Every decision request is recorded with `actor=agent:<id>` and included in hash chain | Low |
| R3 | Operator claims they didn't log in | T6 | Auth events (`auth.login`, `auth.sso`, `auth.mfa_challenge`) audited with IP, user agent, device fingerprint | Low |

### 4.4 Information disclosure

| ID | Threat | Boundary | Mitigation | Residual |
|---|---|---|---|---|
| I1 | One tenant reads another tenant's data | T3 | Row-Level Security enforced via `app.org_id` GUC; all queries executed under per-request session | Low |
| I2 | Leaked database backup | T3 | Backups encrypted with KMS; access restricted to backup-restore role; tested quarterly | Low |
| I3 | Sensitive data in application logs | T2 | Structlog redactor removes email, ip, secrets fields by name; max 2KB body truncation | Medium |
| I4 | Error messages leak internal state | T1 | Pydantic validation returns sanitized errors; stack traces never sent to client | Low |
| I5 | CORS misconfiguration enables credential theft | T1 | CORS restricted to configured origins; no wildcards in production | Low |
| I6 | PII in URL query strings appears in CDN logs | T1 | Sensitive fields only via POST body; linter blocks query-string usage for PII fields | Medium |
| I7 | Memory disclosure via timing in Argon2 verify | T2 | Constant-time comparison; server-side pepper applied after Argon2 digest | Low |

### 4.5 Denial of service

| ID | Threat | Boundary | Mitigation | Residual |
|---|---|---|---|---|
| D1 | Credential-stuffing against login | T1 | Per-IP rate limit; exponential lockout after 5 failed attempts; CAPTCHA after 3 |  Medium |
| D2 | Flooding /decisions/check | T7 | Per-org and per-key rate limits; Redis token bucket; edge WAF | Low |
| D3 | Slowloris / connection exhaustion | T1 | Uvicorn worker limits; idle timeouts; CDN absorbs | Low |
| D4 | Database connection exhaustion | T3 | PgBouncer; per-tenant pool quotas | Low |
| D5 | Expensive ABAC condition explosion | T2 | Condition AST validated for depth ≤ 10; operator whitelist; evaluation time budgeted to 5ms | Low |
| D6 | Log-flood in audit from malicious actor | T7 | Rate limit admin writes; bounded payload size; sampling never applied to deny/require_approval | Low |

### 4.6 Elevation of privilege

| ID | Threat | Boundary | Mitigation | Residual |
|---|---|---|---|---|
| E1 | Agent acts with scopes beyond the supervising user | T7 | Intersection rule: `agent.effective_scopes = assignment ∩ user.role_scopes` enforced at decide() | Low |
| E2 | Privilege escalation via policy injection | T2 | Condition AST is an allow-list of operators; no eval; policies authored via UI/API only — never loaded from untrusted YAML | Low |
| E3 | JWT algorithm confusion (`alg=none`) | T2 | PyJWT configured with explicit algorithm list `["HS256"]`; library rejects `alg=none` | Low |
| E4 | SSO assertion replay | T5 | SAML `NotOnOrAfter` check; OIDC `exp` + `nonce` single-use cache; replay detection window | Low |
| E5 | SQL injection via search params | T3 | SQLAlchemy parameterized queries exclusively; no string formatting | Low |
| E6 | SSRF via webhook test | T2 | Webhook URL validated against blocklist (RFC1918, metadata, link-local); DNS re-resolved inside sandbox | Low |
| E7 | Admin UI CSRF | T6 | SameSite=Strict on refresh; anti-CSRF double-submit for state-changing POSTs | Low |
| E8 | Container escape | T2 | gVisor runtime for worker pods; seccomp profile; non-root containers | Medium |

## 5. Abuse cases specific to AI agents

- **A1 — Scope creep via policy drift.** Agent X gains additional scopes when a new policy is mistakenly set to `allow` globally. *Mitigation:* new policy PRs require security review; simulator-in-loop tests; weekly diffs sent to CISO.
- **A2 — Approval fatigue.** Humans rubber-stamp `require_approval` requests. *Mitigation:* approval UI shows risk score, prior denial rate, and the exact matched policy; mandatory justification field.
- **A3 — Prompt injection causes the agent to escalate.** External content tells the agent "ignore your policies." *Mitigation:* Kynara is outside the LLM's trust boundary — no instruction written into a prompt can change decisions returned by `/decisions/check`. Fail-closed SDK.
- **A4 — Agent killswitch bypass.** An attacker who kills the agent session re-registers a new one. *Mitigation:* `agent.kill` marks the agent disabled (not merely the session); re-enabling requires an admin audit event.

## 6. Open items

| ID | Finding | Due | Owner |
|---|---|---|---|
| O1 | Evaluate mTLS for SDK → backend in high-trust deployments | 2026-Q3 | Platform |
| O2 | Add policy-simulation diff check in PR automation | 2026-Q2 | DX |
| O3 | Formalize abuse-case library into runtime anomaly detection | 2026-Q4 | Detection |
