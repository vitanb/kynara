# ISO/IEC 27001:2022 Statement of Applicability — Kynara

**Version**: 1.0
**Effective**: 2026-04-21
**Owner**: Chief Information Security Officer
**Next review**: 2027-04-21

This Statement of Applicability (SoA) identifies which of the 93 controls listed in Annex A of ISO/IEC 27001:2022 apply to Kynara's Information Security Management System (ISMS), the justification for inclusion or exclusion, and the implementation status.

## Scope

The ISMS covers the development, operation, and support of the Kynara AI Agent Permission System, including associated infrastructure, source code, customer data, and personnel with logical or physical access to those assets. The ISMS is operated from company offices and production AWS regions `us-east-1` and `eu-west-1`.

## Risk treatment summary

A total of 93 Annex A controls were evaluated. 88 are applicable and implemented; 5 are excluded with justification (see the "Excluded" column). Residual risk for each applicable control is tracked in the risk register.

## A.5 Organizational controls (37 controls)

| Control | Title | Applicable | Implementation |
|---|---|---|---|
| A.5.1 | Policies for information security | Yes | Information Security Policy approved by CEO; reviewed annually |
| A.5.2 | Information security roles and responsibilities | Yes | CISO accountable; responsibilities in role charters |
| A.5.3 | Segregation of duties | Yes | Dual approval required for production DB changes and key rotation |
| A.5.4 | Management responsibilities | Yes | Quarterly security steering committee |
| A.5.5 | Contact with authorities | Yes | Documented contacts for law enforcement and regulators |
| A.5.6 | Contact with special interest groups | Yes | FIRST, OWASP, ISACA memberships |
| A.5.7 | Threat intelligence | Yes | Subscription to CISA KEV, vendor advisories, GreyNoise |
| A.5.8 | Information security in project management | Yes | Security review gate in every new product initiative |
| A.5.9 | Inventory of information and other associated assets | Yes | CMDB maintained in Oomnitza |
| A.5.10 | Acceptable use of information and other associated assets | Yes | Acceptable Use Policy acknowledged at onboarding |
| A.5.11 | Return of assets | Yes | Offboarding checklist; remote wipe via MDM |
| A.5.12 | Classification of information | Yes | Four-tier classification: Public, Internal, Confidential, Restricted |
| A.5.13 | Labelling of information | Yes | Automated labelling via DLP; visible in all docs |
| A.5.14 | Information transfer | Yes | Encrypted in transit; legal review for external transfers |
| A.5.15 | Access control | Yes | See CC6 in SOC 2 mapping |
| A.5.16 | Identity management | Yes | Centralized Okta; SCIM for lifecycle |
| A.5.17 | Authentication information | Yes | Argon2id hashing; server-side pepper; MFA mandatory |
| A.5.18 | Access rights | Yes | Quarterly access reviews; automated deprovisioning |
| A.5.19 | Information security in supplier relationships | Yes | Vendor Security Questionnaire; ongoing monitoring |
| A.5.20 | Addressing information security within supplier agreements | Yes | Security addendum in all supplier contracts |
| A.5.21 | Managing information security in the ICT supply chain | Yes | SBOM for every build; dependency pinning; signed containers |
| A.5.22 | Monitoring, review and change management of supplier services | Yes | Annual vendor re-assessment |
| A.5.23 | Information security for use of cloud services | Yes | Cloud Security Policy; documented shared responsibility |
| A.5.24 | Information security incident management planning and preparation | Yes | `/docs/runbooks/incident-response.md` |
| A.5.25 | Assessment and decision on information security events | Yes | Sev classification matrix |
| A.5.26 | Response to information security incidents | Yes | IR team on 24x7 rotation |
| A.5.27 | Learning from information security incidents | Yes | Post-incident reviews; metrics trend quarterly |
| A.5.28 | Collection of evidence | Yes | Forensic tooling; chain of custody template |
| A.5.29 | Information security during disruption | Yes | BCP/DR plan; quarterly drills |
| A.5.30 | ICT readiness for business continuity | Yes | RPO 15 min / RTO 4 hr documented |
| A.5.31 | Legal, statutory, regulatory and contractual requirements | Yes | Compliance register |
| A.5.32 | Intellectual property rights | Yes | OSS license review (ScanCode + FOSSA) |
| A.5.33 | Protection of records | Yes | Audit log hash chain; 7-year retention |
| A.5.34 | Privacy and protection of PII | Yes | DPO appointed; see GDPR DPA |
| A.5.35 | Independent review of information security | Yes | Annual third-party audit; pen test |
| A.5.36 | Compliance with policies, rules and standards for information security | Yes | Drata continuous monitoring |
| A.5.37 | Documented operating procedures | Yes | Runbooks under `/docs/runbooks` |

## A.6 People controls (8 controls)

| Control | Title | Applicable | Implementation |
|---|---|---|---|
| A.6.1 | Screening | Yes | Background checks for all employees and contractors |
| A.6.2 | Terms and conditions of employment | Yes | NDAs + IP assignment in offer letters |
| A.6.3 | Information security awareness, education and training | Yes | Annual + role-based training |
| A.6.4 | Disciplinary process | Yes | HR Progressive Discipline Policy |
| A.6.5 | Responsibilities after termination or change of employment | Yes | NDA survives; offboarding access cut within 5 min |
| A.6.6 | Confidentiality or non-disclosure agreements | Yes | NDAs with all employees, contractors, customers |
| A.6.7 | Remote working | Yes | Managed devices; VPN; encrypted disks |
| A.6.8 | Information security event reporting | Yes | `security@kynara.example.com` monitored 24x7 |

## A.7 Physical controls (14 controls)

| Control | Title | Applicable | Implementation |
|---|---|---|---|
| A.7.1 | Physical security perimeters | Yes | AWS SOC2-attested data centers; corporate offices with badge access |
| A.7.2 | Physical entry | Yes | Badge + visitor escort |
| A.7.3 | Securing offices, rooms and facilities | Yes | Locked server rooms (office); production is cloud-only |
| A.7.4 | Physical security monitoring | Yes | CCTV in offices; AWS monitors DC |
| A.7.5 | Protecting against physical and environmental threats | Yes | Multi-AZ deployment; fire suppression at AWS |
| A.7.6 | Working in secure areas | Yes | Visitor policy; clean desk policy |
| A.7.7 | Clear desk and clear screen | Yes | Auto-lock after 5 min idle |
| A.7.8 | Equipment siting and protection | Yes | Office equipment inventoried; anti-theft cables |
| A.7.9 | Security of assets off-premises | Yes | MDM with encryption; remote wipe |
| A.7.10 | Storage media | Yes | Removable media disabled at endpoint |
| A.7.11 | Supporting utilities | Yes | Data-center UPS (AWS); office battery backup for networking |
| A.7.12 | Cabling security | Excluded | Cloud-native; no customer cabling in scope |
| A.7.13 | Equipment maintenance | Yes | Hardware refresh cycle tracked in CMDB |
| A.7.14 | Secure disposal or re-use of equipment | Yes | Certified wiping (NIST 800-88); shred certificates |

## A.8 Technological controls (34 controls)

| Control | Title | Applicable | Implementation |
|---|---|---|---|
| A.8.1 | User endpoint devices | Yes | MDM (Kandji); EDR (CrowdStrike) |
| A.8.2 | Privileged access rights | Yes | Break-glass access; JIT elevation via IAM Identity Center |
| A.8.3 | Information access restriction | Yes | RLS in Postgres; app-layer authZ |
| A.8.4 | Access to source code | Yes | GitHub + branch protection + signed commits |
| A.8.5 | Secure authentication | Yes | See A.5.17 |
| A.8.6 | Capacity management | Yes | Auto-scaling; capacity forecasting quarterly |
| A.8.7 | Protection against malware | Yes | EDR on hosts; container signing |
| A.8.8 | Management of technical vulnerabilities | Yes | Weekly Trivy/Grype scans; SLA: Critical 7d, High 14d, Medium 30d |
| A.8.9 | Configuration management | Yes | Everything in Terraform; drift detection via `terraform plan` in CI |
| A.8.10 | Information deletion | Yes | Soft-delete + 30-day cryptoshred |
| A.8.11 | Data masking | Yes | Test environments use synthetic data; DLP redaction in logs |
| A.8.12 | Data leakage prevention | Yes | DLP in email and endpoint; egress IP allowlisting |
| A.8.13 | Information backup | Yes | Daily encrypted backups to cross-region object storage |
| A.8.14 | Redundancy of information processing facilities | Yes | Multi-AZ; active-active for stateless; active-passive for RDS |
| A.8.15 | Logging | Yes | Structured JSON logs to central SIEM; audit log in Kynara itself |
| A.8.16 | Monitoring activities | Yes | Prometheus + Grafana + Falco |
| A.8.17 | Clock synchronization | Yes | chrony → AWS NTP fleet |
| A.8.18 | Use of privileged utility programs | Yes | Restricted to admins; logged |
| A.8.19 | Installation of software on operational systems | Yes | Immutable containers; admission policy |
| A.8.20 | Networks security | Yes | VPC isolation; security groups; zero-trust between tiers |
| A.8.21 | Security of network services | Yes | TLS 1.3; AWS Shield; WAF rules |
| A.8.22 | Segregation of networks | Yes | Separate VPCs for prod/stage/dev; no peering to corporate |
| A.8.23 | Web filtering | Yes | Zscaler on endpoints |
| A.8.24 | Use of cryptography | Yes | KMS-managed keys; FIPS-validated libraries |
| A.8.25 | Secure development life cycle | Yes | SDLC with security gates |
| A.8.26 | Application security requirements | Yes | Threat model per feature; SAST/DAST |
| A.8.27 | Secure system architecture and engineering principles | Yes | Defense-in-depth; fail-closed; least privilege |
| A.8.28 | Secure coding | Yes | Semgrep rules; code review checklist |
| A.8.29 | Security testing in development and acceptance | Yes | pytest + integration tests with real DB; OWASP ZAP scans |
| A.8.30 | Outsourced development | Excluded | All development in-house; control re-visits if policy changes |
| A.8.31 | Separation of development, test and production environments | Yes | Separate AWS accounts per environment |
| A.8.32 | Change management | Yes | See SOC 2 CC8.1 |
| A.8.33 | Test information | Yes | Synthetic data only in test; production data never copied |
| A.8.34 | Protection of information systems during audit testing | Yes | Read-only IAM roles for auditors |

## Excluded controls

| Control | Justification |
|---|---|
| A.7.12 Cabling security | Cloud-native service; no customer-facing cabling |
| A.8.30 Outsourced development | No outsourced development; all code written by employees |

## Management approval

Approved by the Information Security Steering Committee on 2026-04-18.
