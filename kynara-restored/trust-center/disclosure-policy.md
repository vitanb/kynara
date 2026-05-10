# Vulnerability disclosure policy

Kynara invites independent researchers to help us improve the security of our service. This page documents the rules of engagement.

## Safe harbor

Activities conducted in good faith and within this policy are authorized — we will not pursue legal action or notify law enforcement. If a third party initiates legal action, we will take reasonable steps to make it known that the activity was authorized.

## In scope

- `*.kynara.example.com` (production and sandbox)
- The `@kynara/*` and `kynara-*` packages on npm and PyPI
- The Kynara SDKs in this repo

## Out of scope

- Findings against AWS, Stripe, Okta, Datadog, or other listed sub-processors — please report directly to the vendor.
- Denial-of-service against production. Use the sandbox.
- Social engineering of Kynara staff or customers.
- Physical attacks against Kynara offices or AWS facilities.
- Reports requiring user interaction that is unrealistic (e.g., "if the victim disables MFA").

## Reporting

Email `security@kynara.example.com` (PGP key in `/.well-known/pgp-key.txt`) or submit via [HackerOne](https://hackerone.com/kynara). Please include:

- A clear description of the issue.
- Reproduction steps.
- Affected URL/host/version.
- Estimated impact.
- Proof-of-concept where safe.

We acknowledge within 1 business day and triage within 5 business days. We commit to remediation within the SLAs below or, if we cannot meet them, to giving you a clear timeline.

## Severity and SLA

| Severity | Remediation SLA |
|---|---|
| Critical | 7 calendar days |
| High | 14 calendar days |
| Medium | 30 calendar days |
| Low | 90 calendar days |

## Disclosure

We follow a 90-day coordinated disclosure window from acknowledgment. We will work with you on extensions if remediation requires customer action.

## Hall of fame

Researchers who report valid issues get a write-up at `trust.kynara.example.com/hall-of-fame` (with permission), a swag pack, and — for issues at High and above — a cash bounty (rates posted on HackerOne).
