# Incident Response Runbook

**Purpose**: to define how Kynara detects, triages, responds to, recovers from, and learns from security and availability incidents.
**Owner**: Security Engineering
**Applies to**: all Kynara production services and personnel with production access.

## 1. Severity classification

| Sev | Examples | MTTA | MTTM target |
|---|---|---|---|
| Sev-1 | Confirmed data exposure; audit chain broken; full outage; active compromise | 5 min | 60 min |
| Sev-2 | Partial outage; suspected compromise; single-tenant confidentiality risk | 15 min | 4 hr |
| Sev-3 | Degraded performance; non-production security finding | 1 hr | 1 business day |
| Sev-4 | Informational; potential future risk | 1 business day | 5 business days |

## 2. Roles during an incident

- **Incident Commander (IC)**: runs the incident. First on-call at Sev-1/2.
- **Scribe**: records timeline in the incident doc.
- **Communications Lead**: handles status-page and customer comms.
- **Security Lead**: for security incidents specifically; pulled in by IC.
- **Executive Sponsor**: CTO for Sev-1; CISO for security Sev-1/2.

## 3. Detection sources

- Prometheus/Alertmanager → PagerDuty (`api_5xx_ratio`, `audit_chain_broken`, `decision_latency_p99`, `auth_failures_ratio`).
- Customer reports via `security@kynara.example.com` or in-app.
- Third-party disclosure via `security.txt` or bug bounty.
- Internal staff observation (`#ops-incidents`).

## 4. Response flow

```
  Alert or report
        │
        ▼
  Page on-call ──── Acknowledge within MTTA
        │
        ▼
  IC declares incident in Slack #inc-YYYYMMDD-NN
        │
        ▼
  Triage: confirm scope, severity, impact
        │
        ▼
  Mitigate: rollback, feature flag, isolate tenant
        │
        ▼
  Eradicate: revoke credentials, patch
        │
        ▼
  Recover: restore service, verify SLOs
        │
        ▼
  Post-incident review within 5 business days
```

## 5. Common playbooks

### 5.1 Audit chain broken (`audit_chain_broken` alert fires)

1. **Do not restart** the backend. Restarting could mask the condition.
2. IC acknowledges; Security Lead paged automatically.
3. Run `POST /api/v1/audit/verify` manually; note the `broken_at` sequence.
4. Snapshot the `audit_events` table to an evidence bucket under `/evidence/<incident-id>/`.
5. Inspect the rows around `broken_at`: compare `entry_hash` recomputation via the standalone verifier in `scripts/verify_chain_offline.py`.
6. If the break is due to application bug, hot-patch the affected entry with an `audit.chain_gap` notice entry that records the gap (rather than rewriting the bad entry — never rewrite).
7. If the break is due to tampering, preserve evidence, rotate DB credentials, engage external forensics.
8. Notify impacted customers within 72 hours per GDPR/HIPAA obligations.

### 5.2 Credential compromise (API key or JWT secret)

1. Rotate the key or secret immediately via IAM admin console.
2. For JWT signing secret: bump `jwt_secret_version`; old tokens are now invalid — users will be forced to re-auth.
3. Query audit log for usage of the compromised credential since suspected compromise time.
4. Revoke derived refresh tokens with `UPDATE auth_sessions SET is_revoked=true WHERE jwt_secret_version < N`.
5. Publish an advisory to affected customers.

### 5.3 Tenant isolation regression

1. Confirm via red-team query that cross-tenant reads are possible.
2. Block the affected endpoint via WAF rule (fail-closed).
3. Hot-fix the RLS policy or application check; deploy via emergency change process.
4. Audit-log scan to determine whether any cross-tenant access occurred.
5. Notify affected customers.

### 5.4 Stripe webhook compromise

1. Rotate the webhook signing secret in Stripe dashboard.
2. Verify no anomalous refunds or subscription changes in the affected window.
3. Reconcile billing metrics against Stripe's authoritative state.

### 5.5 Dependency CVE (Critical)

1. Confirm exploitability against Kynara (not all CVEs are exploitable in context).
2. If exploitable: emergency change process; deploy patched image within 7 calendar days.
3. If not yet exploitable: add to backlog with standard SLA.

## 6. Customer communication

- **Status page** (`status.kynara.example.com`): posted within 30 min of Sev-1 confirmation, updated every 30 min until resolution.
- **Email to account admins**: for any incident affecting their tenant.
- **Public advisory**: for any incident requiring customer action (e.g., credential rotation).
- **Regulatory**: CISO coordinates with Legal for any breach-notification trigger.

## 7. Post-incident review (PIR)

Conducted within 5 business days for Sev-1 and Sev-2. Agenda:

- Timeline reconstruction.
- Contributing factors (technical + process + organizational).
- What worked well.
- What can be improved.
- Action items with owners and dates.
- Metrics update.

PIRs are blameless. They are stored in Confluence `SEC/PIR` and linked from the incident record.

## 8. Evidence handling

- Snapshots to `s3://kynara-evidence/<incident-id>/`, encrypted with KMS key `alias/incident-evidence`.
- Access logged and requires dual approval.
- Chain of custody record started for every Sev-1.

## 9. Drills

- Monthly: on-call page drill (fire non-incident page to verify ack time).
- Quarterly: DR drill (restore from backup to cold region).
- Bi-annually: security tabletop exercise (simulated breach scenario).

## 10. Escalation contacts

| Who | Channel |
|---|---|
| On-call (primary) | PagerDuty `prod-oncall` |
| Security | PagerDuty `sec-oncall`; Slack `#sec-ir` |
| CISO | PagerDuty; mobile on file with ops |
| CTO | PagerDuty; mobile on file with ops |
| Legal | `legal@kynara.example.com` + phone tree |
| External forensics | [Vendor], contract on file with Legal |
