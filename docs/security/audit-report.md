# Internal Security Audit Report — Kynara (Q1 2026)

**Report period**: 2026-01-01 through 2026-03-31
**Report date**: 2026-04-15
**Auditor**: Internal Audit Group (independent reporting line to the Audit Committee)
**Engagement lead**: [Name], CIA, CISA
**Distribution**: CEO, CTO, CISO, Audit Committee of the Board

## 1. Executive summary

Internal Audit reviewed the design and operating effectiveness of selected controls over the quarter, with a focus on access management, change management, data protection, audit log integrity, and third-party risk. Of the 42 controls sampled, 38 are operating effectively, 3 have minor deficiencies, and 1 has a moderate deficiency with a management response in progress. No material weaknesses were identified.

### Summary of findings

| ID | Area | Severity | Status |
|---|---|---|---|
| F-01 | Privileged access — secondary approver time-to-approve | Low | Remediated |
| F-02 | Terraform drift alerting noise | Low | Accepted risk |
| F-03 | Incident runbook version lag for edge cases | Low | Remediated |
| F-04 | Inconsistent SCIM deprovisioning latency for one test tenant | Moderate | In progress (target 2026-05-15) |

## 2. Scope and methodology

Internal Audit sampled controls across the following domains. Sample sizes were calculated using guidance from AICPA AT §501 for attestation samples.

| Domain | Controls sampled | Sample size |
|---|---|---|
| Access management (CC6) | 9 | 25 events each |
| Change management (CC8) | 6 | 40 PRs; 12 deploys |
| System operations (CC7) | 7 | full incident set |
| Encryption & cryptography (A.8.24) | 5 | config review |
| Audit log integrity (PI1.3) | 4 | full period chain verification |
| Third-party risk (A.5.19) | 4 | 12 vendor files |
| Business continuity (A.5.30) | 4 | DR drill + 3 restore tests |
| Incident response (CC7.4) | 3 | 7 incidents + 2 tabletop exercises |

Methodology: direct inspection of evidence; recomputation where possible (e.g., independent chain verification with a separate implementation); interviews with control owners; walkthroughs of the change process.

## 3. Detailed findings

### F-01 Privileged access — secondary approver time-to-approve (Low)
**Observation**: Of 25 sampled production database break-glass requests, 4 (16%) were approved more than 30 minutes after request. The policy sets a 15-minute target.
**Impact**: Delays incident response but does not bypass controls.
**Remediation**: Added approver SLA alerting to PagerDuty; published escalation path. Retested 2026-04-10 with 20 new samples, all within SLA. **Closed.**

### F-02 Terraform drift alerting noise (Low)
**Observation**: Drift-detection pipeline produced 137 alerts over the quarter, of which 128 (93%) were benign (e.g., AWS-side tag mutations). The high noise rate risks desensitization.
**Impact**: Potential missed real drift.
**Management response**: Tuning suppressions in progress. Temporary mitigation: weekly human review of drift report rather than event-based. **Accepted risk** for Q2; reevaluate Q3.

### F-03 Incident runbook version lag for edge cases (Low)
**Observation**: Two of seven incidents referenced runbook sections that had been rewritten in January; on-call used older wiki copies.
**Impact**: Minor confusion; no incident extended by this.
**Remediation**: Runbook index now served from a single source of truth; old copies redirect. **Closed.**

### F-04 Inconsistent SCIM deprovisioning latency (Moderate)
**Observation**: For one test tenant configured with Azure AD, SCIM deprovisioning took 42 minutes (vs. 5-minute target) in 2 of 5 simulated terminations. The root cause is a missing webhook registration for the delete event in the Azure AD app manifest template.
**Impact**: Terminated employees retain access longer than policy permits.
**Management response**: Patch to Azure-AD provisioning template staged for 2026-05-15 release. Until then, daily automated reconciliation job will sweep for orphaned users. **In progress.**

## 4. Positive observations

- **Audit log integrity**: Independent recomputation of the hash chain for the full 128,417,392 events in Q1 returned `ok=true` with matching tip hash. No discrepancies detected.
- **Change management**: 100% of sampled PRs had at least one approving reviewer; 87% had two or more; zero direct pushes to `main` were observed.
- **Secrets management**: No secrets found in source code via Gitleaks scan across all 14 repositories.
- **Backup restore**: All three sampled restores completed within the 4-hour RTO target (best 38 minutes, worst 2h 17m).
- **Incident response**: Mean time to acknowledge across 7 incidents was 3.2 minutes (target: ≤5 min). All incidents had a post-incident review completed within 5 business days.

## 5. Trend analysis vs. Q4 2025

| Metric | Q4 2025 | Q1 2026 | Direction |
|---|---|---|---|
| Open Sev-1 findings | 1 | 0 | Improving |
| Total findings | 6 | 4 | Improving |
| MTTR for Sev-2 incidents | 3.8 hr | 2.1 hr | Improving |
| Change failure rate | 2.1% | 1.6% | Improving |
| Access review completion | 94% | 99% | Improving |
| Vulnerability backlog (Critical + High) | 11 | 4 | Improving |

## 6. Management assertion

Management represents that it has implemented controls as described in the SOC 2 mapping and ISO 27001 SoA, and that no material control failures went unreported to Internal Audit during the period. Management commits to remediation of F-04 by the stated date.

## 7. Distribution and next report

This report is distributed to the named recipients under confidentiality. The next quarterly report (Q2 2026) is due 2026-07-15.

---

**Signatures**

Internal Audit Lead: __________________________ Date: __________

CISO: __________________________ Date: __________

Audit Committee Chair: __________________________ Date: __________
