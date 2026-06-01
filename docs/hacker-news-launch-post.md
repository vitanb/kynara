# Hacker News Launch Post

## Title
Show HN: Kynara – Permission control plane for AI agents (RBAC + ABAC + tamper-evident audit)

---

## Post Body

I've been building production AI agent systems for the past year, and the same problem keeps
coming up: once an agent can call real APIs — write to a database, send emails, issue refunds,
restart services — you immediately need to answer questions that none of the agent frameworks
address:

- Which agents are allowed to do what, and under what conditions?
- Can agent A act on behalf of user B, and if so, does it inherit B's restrictions or can it
  exceed them?
- Who approved this action, and can we prove it wasn't tampered with after the fact?
- When something goes wrong, can we replay what happened and see exactly which policy matched?

IAM systems (AWS IAM, OPA, Casbin) weren't designed for the agent trust model. The problem
isn't just "does this principal have permission for this action" — it's "does this agent,
acting on behalf of this user, under these runtime conditions, using this specific tool, have
permission right now?" That's a richer evaluation surface, and the answers need to be
auditable in a way that satisfies a compliance team, not just a developer.

So I built Kynara. Here's what it actually is:

**The core primitive** is a decision API: your agent calls `POST /decisions/check` with a
subject, action, resource (with typed attributes), and ambient context (time, IP, user role,
etc.). The policy engine evaluates RBAC + ABAC rules and returns `allow`, `deny`, or
`require_approval`. Every decision is appended to a SHA-256 hash-chained audit log. Any
tampering with a past record breaks the chain and is detected on the next integrity check.

**The non-escalation guarantee** is the part I'm most proud of: if an agent is acting on
behalf of a user, its effective permissions are the intersection of the agent's roles and the
user's roles. An agent can never acquire more authority than the human who dispatched it,
regardless of how permissive its own policies are. This prevents a whole class of privilege
escalation via agent impersonation.

**The human-in-the-loop flow** is a first-class outcome, not a bolt-on. When a policy returns
`require_approval`, the agent pauses and gets back an approval URL. A human reviews the queued
request (with full context: which agent, which action, which resource, what the risk score is,
what the agent's historical denial rate is) and approves or rejects. The agent resumes or
aborts. Approvals expire after 24 hours by default.

**JIT grants** cover break-glass scenarios: an operator can grant a time-bound, scoped
permission elevation with a justification and ticket URL. The grant widens the agent's
effective scopes for its duration without touching any permanent policy. Every grant is
recorded in the audit chain.

**Policy replay** is the thing I wanted most before I built it: before deploying a policy
change, you can simulate it against up to 30 days of real historical decisions to see exactly
what would flip — how many `allow` → `deny`, how many `allow` → `require_approval` — before
any live agent is affected.

**The SDKs** wrap the decision API so enforcement happens at the tool boundary, before any
side effect:

```python
@permission_required("payments.refund.issue", resource_arg="refund_id")
def issue_refund(refund_id: str, amount_cents: int):
    return stripe.refund(refund_id, amount_cents)
```

If the decision is `deny`, the decorator raises `PermissionDenied` before the function body
runs. There's a LangChain callback handler, an AutoGen wrapper pattern, a CrewAI guard
decorator, and an Express middleware for the TypeScript side. A Go sidecar handles
high-throughput workloads at sub-millisecond latency by evaluating a locally-cached,
JWS-signed policy bundle and streaming decisions back to the central audit log in batches.

**What's production-ready**: the policy engine, auth (Argon2id + JWT + rotating refresh
tokens + API keys), multi-tenant Postgres schema with RLS, the audit chain, Stripe billing,
Okta/SAML SSO, SCIM, the Python and TypeScript SDKs, the Go sidecar, and the full admin UI.

**What's not done yet**: the self-serve onboarding flow needs work, the mobile layout of the
UI is rough, and the Go sidecar hasn't been load-tested beyond synthetic benchmarks. I'm also
building out the anomaly detection layer (deny-rate z-score alerting and geo-jump detection
are in, cross-org baselines aren't yet).

The repo is source-available under BSL 1.1. Happy to answer questions about the design,
the trust model, how the policy engine works, or anything else.

Demo: https://kynaraai.com
Docs: https://kynaraai.com/docs

---

## Notes for posting

- Post as a **Show HN** — not a regular submission
- Post on a Tuesday/Wednesday at 8–9 AM EST for peak visibility
- In the comments, proactively address: "how is this different from OPA/Casbin?" and
  "why not just use AWS IAM?"
- Be ready to discuss the BSL license choice — HN has strong opinions on this
- Have a link to a live demo ready; engineers will want to click something

## Anticipated tough questions (prepare answers)

**"Why not just use OPA?"**
OPA evaluates policies against data you provide. Kynara is a full system: it stores the
policies, manages the principal identities (agents, users), enforces the non-escalation
invariant across the subject hierarchy, maintains the tamper-evident audit chain, manages
approval workflows, and provides the human review UI. OPA is an evaluation engine; Kynara
is the control plane built on top of that pattern.

**"Why BSL and not MIT/Apache?"**
BSL lets us offer the full source for self-hosting and inspection while protecting against
a cloud provider wrapping it as a managed service without contributing back. It converts to
Apache 2.0 after 4 years. All the SDKs are MIT.

**"Isn't this just re-implementing IAM?"**
Traditional IAM is designed for human-to-service access. The agent trust model adds a new
dimension: an agent acting on behalf of a user creates a delegation chain where the effective
authority is bounded by both the agent's grants and the user's grants simultaneously. Standard
IAM systems have no native model for this intersection semantics.

**"How does this handle prompt injection?"**
Kynara sits entirely outside the LLM's trust boundary. The policy engine evaluates
structured data (subject, action, resource, context) — not natural language. A prompt
injection attack inside the LLM cannot modify what Kynara receives or how it evaluates it.
The guardrails layer adds a secondary defense: if an agent starts making unusual patterns
of requests (deny-rate spike, geo-jump), it gets auto-revoked.
