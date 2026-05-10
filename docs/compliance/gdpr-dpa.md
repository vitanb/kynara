# Data Processing Addendum (GDPR / UK GDPR)

**Between**: Kynara, Inc. ("Processor", "Kynara", "we", "us")
**And**: the Customer identified in the Order Form ("Controller", "Customer", "you")
**Effective**: the later of the Order Form effective date or this DPA's execution date.

This Data Processing Addendum ("DPA") supplements the Master Subscription Agreement ("MSA") between the parties. It reflects the parties' agreement on the Processing of Personal Data by Kynara on behalf of Customer and forms part of the MSA. If there is any conflict between this DPA and the MSA, this DPA governs with respect to the Processing of Personal Data.

## 1. Definitions

Terms used but not defined herein have the meanings given in Regulation (EU) 2016/679 ("GDPR") and, where applicable, the UK GDPR and the UK Data Protection Act 2018. "Standard Contractual Clauses" or "SCCs" means the clauses annexed to Commission Implementing Decision (EU) 2021/914 of 4 June 2021 (the EU SCCs) and the UK International Data Transfer Addendum ("UK IDTA") issued by the UK Information Commissioner.

## 2. Subject matter and duration of Processing

Kynara will Process Personal Data to provide the Kynara service — a policy evaluation, authorization, and audit logging platform for AI agents — for the term of the Order Form and for such additional period as required by applicable law.

## 3. Nature and purpose of Processing

Kynara Processes Personal Data as instructed by Customer in order to:

- Authenticate Customer's end users (human operators of AI agents);
- Evaluate authorization decisions when agents act on behalf of end users or Customer;
- Write tamper-evident audit logs of decisions;
- Operate billing, support, and service monitoring.

## 4. Categories of data subjects

- Customer's employees, contractors, and agents that log in to or are referenced in the Kynara service.
- End users of Customer's AI agents, to the extent Customer submits their data in DecisionRequests.

## 5. Categories of Personal Data

- Identity data: name, email, user ID, IP address, device identifier.
- Authentication data: password hash (Argon2id), MFA state, SSO attributes.
- Usage data: API requests, decision records, audit events, approval flow metadata.
- Any additional Personal Data that Customer submits in `resource.attrs` or `context` of DecisionRequests. Customer is responsible for ensuring such submissions have a lawful basis.

Kynara does not Process special categories of Personal Data (Article 9 GDPR) or data relating to criminal convictions (Article 10) by design. If Customer submits such data, Customer represents it has obtained any required additional consents.

## 6. Controller and Processor obligations

### 6.1 Customer's role
Customer is the Controller. Customer will: (a) only submit Personal Data that it is lawfully permitted to; (b) determine the purposes and means of Processing; (c) respond to data subject rights requests, using Kynara's self-service export and deletion tools.

### 6.2 Kynara's role
Kynara is the Processor. Kynara will Process Personal Data only (a) on documented instructions from Customer, including the MSA, this DPA, and Customer's use of the service; and (b) as required by applicable law, in which case Kynara will inform Customer unless prohibited.

### 6.3 Confidentiality
Kynara ensures that persons authorized to Process the Personal Data are subject to confidentiality obligations by contract or statutory duty.

## 7. Security of Processing (Article 32)

Kynara implements appropriate technical and organizational measures ("TOMs"), including:

| Domain | Control |
|---|---|
| Encryption | TLS 1.3 in transit; AES-256-GCM at rest; per-tenant data keys via KMS |
| Access control | SSO + MFA for all personnel; RBAC; least privilege; JIT elevation |
| Tenant isolation | Postgres Row-Level Security (`app.org_id` session GUC); separate data keys |
| Integrity | Hash-chained audit log with SHA-256 chaining and `verify_chain()` endpoint |
| Availability | Multi-AZ; daily backups to cross-region object storage; RPO 15 min / RTO 4 hr |
| Resilience | Quarterly disaster recovery drills |
| Testing | Annual third-party pen test; continuous SAST/DAST/SCA |
| Secure SDLC | Mandatory peer review; threat models; signed commits; signed containers |
| Vulnerability management | Weekly scans; SLAs: Critical 7d, High 14d, Medium 30d |
| Personnel | Background checks; annual training; NDAs |

Full TOM details are maintained in the Trust Center at `trust.kynara.example.com`.

## 8. Sub-processors

### 8.1 General authorization
Customer grants Kynara a general authorization to engage Sub-processors listed at `trust.kynara.example.com/subprocessors` (the "Sub-processor Page").

### 8.2 Notification of changes
Kynara will post new Sub-processors on the Sub-processor Page at least 30 days before onboarding. Customer may subscribe to change notifications. Within 30 days of notice, Customer may object in writing for reasonable, documented data-protection reasons; the parties will then work in good faith to address the objection, failing which Customer may terminate the affected portion of the service.

### 8.3 Sub-processor obligations
Kynara imposes on each Sub-processor written data-protection terms substantially similar to those in this DPA, including Article 28(3) obligations.

### 8.4 Current Sub-processors

| Sub-processor | Purpose | Region | Safeguard |
|---|---|---|---|
| Amazon Web Services, Inc. | Hosting, compute, storage | US, EU, UK | AWS DPA; SCCs as needed |
| Stripe, Inc. | Billing, payment processing | US, EU | Stripe DPA; SCCs |
| Okta, Inc. | Identity provider (optional) | US | Okta DPA; SCCs |
| Datadog, Inc. | Observability, monitoring | US, EU | Datadog DPA; SCCs |

## 9. International data transfers

### 9.1 EU → third country transfers
Where Kynara transfers Personal Data out of the EEA to a country not benefitting from a European Commission adequacy decision, the EU SCCs are hereby incorporated into this DPA. Module Two (Controller to Processor) applies where Customer is a controller; Module Three (Processor to Processor) applies where Customer is itself a processor.

### 9.2 UK transfers
For Personal Data subject to the UK GDPR, the UK IDTA (version B1.0) is hereby incorporated by reference.

### 9.3 Transfer Impact Assessment (TIA)
Kynara has conducted a TIA for the transfers contemplated under this DPA. A summary is available on request to the DPO.

## 10. Data subject rights (Articles 15–22)

Kynara provides, as part of the service:

- A self-service data export API returning a machine-readable archive of a given user's records;
- A self-service deletion API triggering soft-delete plus 30-day cryptoshred;
- A tool to rectify Personal Data records on Customer's instruction;
- Automated decision review: audit log entries for every `allow`/`deny`/`require_approval` decision, satisfying Article 22(3) information rights.

Kynara will assist Customer in responding to data subject rights requests within 5 business days.

## 11. Personal Data Breach (Articles 33 & 34)

Kynara will notify Customer without undue delay and in any event within 72 hours of becoming aware of a Personal Data Breach affecting Customer data. The notification will include, to the extent known: nature of the breach, categories and approximate number of data subjects and records concerned, likely consequences, and measures taken or proposed. Customer is responsible for regulator and data subject notification.

## 12. Data Protection Impact Assessment (Article 35) and prior consultation (Article 36)

Kynara will provide reasonable assistance to Customer in connection with DPIAs and prior consultations with supervisory authorities, taking into account the nature of Processing and information available to Kynara.

## 13. Audit rights (Article 28(3)(h))

Kynara makes available to Customer, on request and under NDA:

- The latest SOC 2 Type II report;
- The latest ISO/IEC 27001 certificate and Statement of Applicability;
- The latest third-party penetration test executive summary;
- The Sub-processor list and TIAs.

No more than once every 12 months (and not unless regulator-required or following a Personal Data Breach), Customer or a mutually agreed third-party auditor may conduct an on-site audit of Kynara's facilities subject to reasonable advance notice and confidentiality.

## 14. Return or deletion of Personal Data

Upon termination or expiry of the MSA, Kynara will, at Customer's choice, return or delete all Personal Data within 30 days, except where retention is required by applicable law. Audit log entries may be retained for up to seven years in encrypted form to satisfy integrity and regulatory commitments; such data is cryptoshredded at the end of the retention period.

## 15. Liability

Each party's liability arising out of or in connection with this DPA is subject to the limitations of liability set out in the MSA.

## 16. Governing law and jurisdiction

This DPA is governed by the law, and subject to the jurisdiction, set out in the MSA, except where mandatory EU/UK law prescribes otherwise for the SCCs/IDTA.

---

**Signature page**

By signing below, the parties agree to be bound by this DPA.

Customer:
Name: _______________________
Title: _______________________
Date: _______________________

Kynara, Inc.:
Name: _______________________
Title: _______________________
Date: _______________________
