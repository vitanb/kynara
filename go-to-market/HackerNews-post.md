# Kynara — HackerNews launch post

*HN rewards technical honesty and punishes marketing. Lead with the problem, be specific, admit limits, and invite criticism. Post Tue–Thu ~8–10am ET. Be at your keyboard for the first 2 hours to answer every comment.*

---

## Title (pick one — keep it plain, no hype)

**Primary (Show HN):**
> Show HN: Kynara – Authorization and audit for AI agents that take real actions

**Alternates:**
> Show HN: Kynara – A permission control plane for AI agents (allow/deny/approve per action)
> Show HN: Authorization for AI agents – identity tells you who, not what they can do

*Notes: "Show HN" requires something people can try (your sandbox/quickstart counts). Keep ≤80 chars. Avoid "revolutionary/powerful/enterprise-grade" — HN allergic to it.*

---

## Body (the post text)

> We've been building Kynara, an authorization and audit layer for AI agents that take real actions — calling APIs, running infra changes, posting to Slack, moving money.
>
> The thing that pushed us to build it: most "agent governance" today is really *identity* (authenticate the agent, give it a token). But a token isn't a permission model. Once an agent has credentials, nothing decides whether *this specific action, right now, in this context* should be allowed. And because the decision is being made by an LLM, "just prompt it not to" isn't a control — a prompt injection or a confused chain can talk it into anything.
>
> So Kynara sits outside the model. Your agent (or a gateway in front of it) calls a decision API with structured data — subject, action, resource, context — and gets back allow / deny / require_approval before the side effect runs. Specifically:
>
> - RBAC + ABAC: an action needs a role that grants the scope (gate), then policy conditions evaluate (e.g. only this Slack channel; recipient must end with @yourcompany.com; business hours only).
> - Non-escalation: an agent's effective permissions are the intersection of the agent's roles and the user who dispatched it — it can't do more than the human behind it.
> - Human-in-the-loop: high-risk actions return require_approval and pause for a person.
> - Tamper-evident audit: every decision is appended to a SHA-256 hash-chained log, so altering a past entry breaks the chain (useful for SOC 2 / EU AI Act Article 12).
> - Two ways to enforce: a Python/TS SDK (decorator + framework callbacks for LangChain/LangGraph/CrewAI/AutoGen), or an MCP gateway that authorizes every tool call and only advertises tools an agent is allowed to use (least-privilege discovery), so you don't change agent code.
>
> Design decisions / things we got wrong at first:
> - Fail-closed by default. Early on we failed open on engine timeouts "for availability" — wrong call for a control plane. Now the SDK denies if it can't reach Kynara (configurable per MCP server).
> - Evaluating natural language was a dead end; everything is structured requests so the policy surface is auditable.
> - The RBAC gate running *before* policy surprised people (you can write a perfect policy and still get denied because no role grants the scope). We kept it but made the trace explain it.
>
> It's source-available (BSL 1.1) so you can self-host and read the whole thing; SDKs are MIT.
>
> Honest limitations: it adds a network hop on the hot path (we cache and there's a local sidecar for sub-ms, but it's a real tradeoff); policy authoring has a learning curve; and we're early — small team, looking for design partners running agents in production.
>
> Try it: [sandbox link] · Docs: [docs link] · Repo: [repo link]
>
> Would love feedback, especially from people running action-taking agents in prod: where does this break, and what would you never put behind a remote authorization call?

---

## First comment (post immediately after submitting — context HN expects)

> Author here. Quick context on where this fits vs. things people will reasonably ask about:
>
> - vs. OPA/Cerbos: those are policy *engines* — great at evaluating a rule. Kynara is the control plane around that: agent identities, non-escalation, approval workflows, the audit chain, and the MCP/SDK enforcement points. You could implement a slice of this on OPA; we wanted the agent-specific parts batteries-included.
> - vs. identity platforms (Okta and the new wave of "identity for agents"): complementary. They answer *who the agent is*; we answer *what it's allowed to do on this call*. We actually sync agent identities in from Okta and make the per-action decision on top.
> - "Why not just scope the API token?" You can, coarsely. But you can't express "only refunds under $X, during business hours, and route anything to an external recipient to a human" as a token scope — that's the gap.
>
> Happy to go deep on the threat model, the hash-chained log, or the MCP gateway internals.

---

## Answering-comments cheat sheet (have these ready)

- **"This is just RBAC with extra steps."** → RBAC is the gate; the value is ABAC conditions on *action arguments* (channel, recipient, amount), non-escalation, approvals, and the audit chain — and that it's enforced at the tool boundary for agents specifically.
- **"Latency?"** → Decision API is a fast structured eval; reads are cached; a local sidecar gives sub-ms for hot paths. It's a real tradeoff and we're upfront about it.
- **"Fail-open or fail-closed?"** → Fail-closed by default; per-server configurable. Explain why we changed it.
- **"Prompt injection can bypass it."** → It can't change what the engine receives — decisions are made on structured requests outside the model, at the tool boundary. Injection might make the agent *try* a bad action; Kynara denies it.
- **"Self-host / lock-in?"** → Source-available (BSL 1.1), full stack runs in your env; SDKs MIT.
- **"How is this different from <competitor that launched this week>?"** → Stay gracious: that's identity; this is authorization + enforcement; they're complementary. Don't trash anyone — HN hates it and it reads as insecure.

## Do / Don't on HN
- DO reply to every top-level comment in the first 2 hours; HN ranking rewards engagement velocity.
- DO concede good criticism openly ("yep, that's a weakness, here's our plan").
- DON'T use marketing adjectives, don't argue, don't downvote critics, don't ask for upvotes anywhere (fastest way to get flagged).
- DON'T submit and disappear. Block 3 hours.

## Cross-post timing (after HN settles)
- r/AI_Agents and r/LocalLLaMA: reframe as a discussion ("How are you handling permissions for agents that take actions?") not a launch.
- LinkedIn: the "identity isn't authorization" angle, linking the blog post.
