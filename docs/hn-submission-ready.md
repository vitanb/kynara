# Kynara — Show HN submission (paste-ready)

## URL field
https://kynaraai.com

## Title (pick one — all under HN's 80-char limit)
1. Show HN: Kynara – Permission control plane for AI agents
2. Show HN: Kynara – Stop AI agents from exceeding the user who dispatched them
3. Show HN: Kynara – RBAC/ABAC + tamper-evident audit for AI agent actions

Recommended: **#1** (clear), or **#2** if you want the novel hook in the title.

---

## Post body

I build production AI agents, and the same gap keeps showing up: the moment an agent can call real APIs — write to a database, send email, issue a refund, restart a service — you need to control *what it's allowed to do, on whose behalf, and under what conditions* — and prove it afterward. Agent frameworks don't address this, and IAM/OPA/Casbin weren't designed for the agent trust model.

Kynara is a permission control plane for AI agents. The core is a decision API: your agent calls `POST /decisions/check` with a subject, action, resource (with typed attributes), and runtime context (time, IP, user role). The engine evaluates RBAC + ABAC rules and returns `allow`, `deny`, or `require_approval`. Every decision is appended to a SHA-256 hash-chained audit log — tampering with any past record breaks the chain and is caught on the next integrity check.

The part I'm proudest of is the **non-escalation guarantee**: when an agent acts on behalf of a user, its effective permissions are the *intersection* of the agent's roles and the user's roles. An agent can never acquire more authority than the human who dispatched it, no matter how permissive its own policy is. That eliminates a whole class of privilege-escalation-via-impersonation.

A few things that fell out of actually using it:

- `require_approval` is a first-class outcome, not a bolt-on. The agent pauses and gets an approval URL; a human reviews full context (which agent, action, resource, risk score, the agent's historical denial rate) and approves or rejects; the agent resumes or aborts.
- **Policy replay**: before shipping a policy change, simulate it against up to 30 days of real historical decisions to see exactly what would flip (allow→deny, allow→require_approval) before a single live agent is affected.
- **JIT grants** for time-boxed break-glass elevation — scoped, justified, recorded in the audit chain, auto-expiring.
- Enforcement happens at the **tool boundary** via SDKs (Python decorator, TS/Express middleware, LangChain/AutoGen/CrewAI adapters) — on a `deny`, the side effect never runs. A Go sidecar does sub-millisecond decisions from a signed, locally-cached policy bundle and batches decisions back to the central audit log.

It sits entirely outside the LLM's trust boundary — it evaluates structured data (subject/action/resource/context), not natural language — so a prompt injection inside the model can't change what Kynara receives or how it decides.

Honest status — what's solid: the policy engine, auth (Argon2id + JWT + rotating refresh tokens + API keys), multi-tenant Postgres with RLS, the audit chain, Okta/SAML SSO + SCIM, Stripe billing, the Python/TS SDKs, the Go sidecar, and the admin UI. What still needs work: self-serve onboarding, the mobile layout, and load-testing the sidecar beyond synthetic benchmarks.

Source-available under BSL 1.1 (converts to Apache 2.0 after 4 years; the SDKs are MIT).

Demo: https://kynaraai.com · Docs: https://kynaraai.com/docs

I'd love feedback on the trust model and the policy engine — happy to go deep on any of it.

---

## First comment to post yourself (seeds the FAQ, ~30s after submitting)

A few questions I expect, answered up front:

**Why not just use OPA?** OPA is an evaluation engine — you hand it policies and data. Kynara is the control plane around that pattern: it stores policies, manages agent/user identities, enforces the non-escalation invariant across the delegation chain, maintains the tamper-evident audit log, runs the approval workflows, and ships the human-review UI.

**Isn't this re-implementing IAM?** Traditional IAM models human→service access. The agent model adds delegation: agent-acting-on-behalf-of-user, where effective authority is bounded by *both* sets of grants at once. Standard IAM has no native model for that intersection.

**Prompt injection?** Out of scope for the LLM to bypass — Kynara evaluates structured requests, not prompts. The guardrails layer adds a second line: anomalous request patterns (deny-rate spikes, geo-jumps) trigger auto-revoke.

**Why BSL?** Full source for self-hosting and inspection, while preventing a cloud provider from reselling it as a managed service without contributing back. SDKs are MIT.

---

## Posting tips
- Submit as **Show HN** (the title prefix does it). Put the demo in the URL field; the body goes in the text box.
- Best window: Tue–Thu, ~8–10am US Eastern. Don't ask friends to upvote — HN penalizes voting rings.
- Reply fast and substantively for the first 1–2 hours; that's what drives ranking.
- Have the live demo working and a clear "try it without signup" path if possible — engineers will click immediately.
