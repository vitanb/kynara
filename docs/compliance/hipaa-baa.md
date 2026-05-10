# HIPAA Business Associate Agreement (BAA) — Kynara

**Covered Entity or Business Associate ("Customer")**: as identified in the Order Form.
**Business Associate ("Kynara")**: Kynara, Inc.
**Effective**: the later of the Order Form effective date and execution of this BAA.

This Business Associate Agreement ("BAA") is entered into pursuant to the Health Insurance Portability and Accountability Act of 1996, as amended by the HITECH Act, and the regulations promulgated thereunder at 45 C.F.R. Parts 160 and 164 (collectively, "HIPAA"). It supplements the MSA and governs Kynara's Processing of Protected Health Information ("PHI") on behalf of Customer. Capitalized terms not defined herein have the meaning given in HIPAA.

## 1. Permitted uses and disclosures

Kynara may use and disclose PHI only:

- to perform functions, activities, or services for Customer as described in the MSA and this BAA;
- as required by law;
- for Kynara's proper management and administration, provided that (i) the disclosure is required by law, or (ii) Kynara obtains reasonable assurance that PHI will be held in confidence and further disclosed only as required by law, and the recipient notifies Kynara of any breach;
- to provide data aggregation services relating to the healthcare operations of Customer (45 C.F.R. §164.504(e)(2)(i)(B)).

## 2. Prohibited uses and disclosures

Kynara will not:

- use or further disclose PHI other than as permitted by this BAA or as required by law;
- sell PHI except as permitted by 45 C.F.R. §164.502(a)(5)(ii);
- use or disclose PHI for marketing, except as permitted in the HITECH Act.

## 3. Safeguards

Kynara will implement administrative, physical, and technical safeguards reasonably and appropriately protecting the confidentiality, integrity, and availability of PHI as required by 45 C.F.R. §§164.308, 164.310, 164.312, and 164.316. Key measures include:

- **Access control (§164.312(a))** — Unique user identification; automatic session lockout (15 min access token); emergency kill for agents; role-based access; encryption at rest (AES-256) and in transit (TLS 1.3).
- **Audit controls (§164.312(b))** — Hash-chained audit log; tamper-evident verification endpoint; retention for minimum of six years.
- **Integrity controls (§164.312(c))** — Cryptographic hashing of audit records; canonical JSON serialization; append-only Postgres trigger on audit table.
- **Person or entity authentication (§164.312(d))** — Argon2id password hashing; MFA; SSO/SAML support.
- **Transmission security (§164.312(e))** — TLS 1.3; certificate pinning for internal service calls; HSTS with preload.
- **Administrative safeguards (§164.308)** — Workforce training; sanction policy; periodic technical and non-technical evaluation (SOC 2 + pen test); contingency plan (BCP/DR with RPO 15 min / RTO 4 hr).
- **Physical safeguards (§164.310)** — Hosting at AWS (HIPAA-eligible), no customer PHI stored on workstations.

## 4. Reporting security incidents and breaches

### 4.1 Security incidents
Routine unsuccessful attempts to breach security (e.g., pings, port scans) are reported to Customer in aggregate form in Kynara's Trust Center. No per-event notification is required for such unsuccessful attempts; this notice serves as the standing notice required by 45 C.F.R. §164.314(a)(2)(i)(C).

### 4.2 Breaches of Unsecured PHI
Kynara will notify Customer of a Breach of Unsecured PHI without unreasonable delay and in no case later than 30 calendar days after discovery, in accordance with 45 C.F.R. §164.410. Notification will include, to the extent known: identification of each affected individual; nature of the Breach; dates of the Breach and discovery; description of unsecured PHI involved; and steps taken to investigate, mitigate, and prevent recurrence.

## 5. Subcontractors

Kynara will ensure that any subcontractor that creates, receives, maintains, or transmits PHI on behalf of Kynara agrees in writing to restrictions and conditions at least as stringent as those in this BAA, as required by 45 C.F.R. §164.502(e)(1)(ii). Current subcontractors processing PHI on behalf of Customer are listed on the Trust Center; additions follow the change-notification process in the GDPR DPA §8.

## 6. Access, amendment, and accounting of disclosures

Upon Customer's request and within 30 days:

- Kynara will make PHI in a Designated Record Set available to Customer to satisfy 45 C.F.R. §164.524;
- Kynara will make amendments Customer directs pursuant to §164.526;
- Kynara will provide an accounting of disclosures pursuant to §164.528.

The Kynara audit log is designed to satisfy §164.528 reporting requirements; filtered reports can be exported as signed Parquet or CSV.

## 7. Availability of internal records

Kynara will make its internal practices, books, and records relating to the use and disclosure of PHI available to the Secretary of Health and Human Services ("HHS") for purposes of determining compliance.

## 8. Return or destruction of PHI

Upon termination of the MSA, Kynara will, if feasible, return or destroy all PHI in its possession within 30 days. Where return or destruction is infeasible (for instance, because PHI is embedded in hash-chained audit records that must be retained for integrity), Kynara will extend the protections of this BAA to such PHI for as long as it is retained and limit further uses and disclosures to those purposes that make return or destruction infeasible.

## 9. Mitigation

Kynara agrees to mitigate, to the extent practicable, any harmful effect that is known to Kynara of a use or disclosure of PHI in violation of the requirements of this BAA.

## 10. Term and termination

This BAA is effective as of the Effective Date and continues until the MSA terminates. Customer may terminate the MSA and this BAA for a material breach by Kynara if Kynara does not cure the breach within 30 days of notice.

## 11. Amendment

The parties agree to take such action as is necessary to amend this BAA from time to time as necessary to comply with changes in applicable law.

## 12. Interpretation

Any ambiguity in this BAA will be resolved to permit the parties to comply with HIPAA.

## 13. Survival

The respective rights and obligations of Kynara under Sections 4, 7, and 8 will survive termination of this BAA.

---

**Signature page**

Customer:
Name: _______________________
Title: _______________________
Date: _______________________

Kynara, Inc.:
Name: _______________________
Title: _______________________
Date: _______________________
