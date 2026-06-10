# Non-Human Identity for AI Agents: What It Is and Why It's Now a Security Priority

### Machine identities already outnumber human ones. AI agents are the fastest-growing — and least governed — class of them.

For every human in your organization, there are now dozens of *non-human* identities: service accounts, API keys, OAuth tokens, CI/CD bots, and increasingly, **AI agents.** Security teams have spent the last few years waking up to "non-human identity" (NHI) as a category that's bigger, faster-growing, and riskier than the human identity estate they've governed for decades. AI agents are the newest entrant — and they break several assumptions NHI tooling was built on.

Here's what non-human identity means, why AI agents are a distinct and harder problem, and what good governance looks like.

---

## What is non-human identity?

Non-human identity covers any identity that isn't a person: service accounts, machine accounts, API keys, secrets, certificates, workload identities, and bots. They authenticate to systems and take actions, just like users — but there are far more of them, they're often created ad hoc, and they frequently outlive the project that spawned them. The result is *sprawl*: thousands of credentials, many over-permissioned, many with no clear owner, many that no one would notice if they were abused.

AI agents are now a first-class member of this category — and identity providers like Okta and Microsoft Entra have started issuing first-class **agent identities** to track them.

---

## Why AI agents are a harder NHI problem

A traditional NHI — say, a service account that syncs two databases — does one narrow, predictable thing. An AI agent is different in ways that matter for security:

- **It acts autonomously.** It decides what to do next, in a loop, often thousands of times a day.
- **It acts on behalf of users.** An agent frequently operates *as a delegate* — which means its effective authority should be bounded by the user who dispatched it, a concept classic NHI tooling has no model for.
- **It has broad reach.** Through tools and MCP servers, a single agent can touch many systems — far more than a typical service account.
- **It's non-deterministic and manipulable.** Its behavior is driven by an LLM that can be prompt-injected, so you can't assume it will only do what it was designed to do.

So "give the agent an identity and rotate its key" — the NHI playbook — is necessary but nowhere near sufficient.

---

## The risks when agents are ungoverned

- **Over-permissioning.** Agents are granted broad access "just in case," violating least privilege from day one.
- **No lifecycle.** Agents get created for experiments and never deprovisioned; their credentials linger.
- **No ownership.** When an agent misbehaves, no one is sure who owns it or what it's allowed to do.
- **No runtime control.** Even with an identity, nothing decides *per action* whether a given call should be allowed.
- **Weak audit.** Reconstructing what an agent did — and proving the record is intact — is hard without purpose-built logging.

---

## What good NHI governance for AI agents looks like

1. **Identity and inventory.** Every agent has a managed identity and shows up in an inventory you can see and own — ideally synced from your IdP.
2. **Least privilege.** Agents get the minimum scopes they need, not broad standing access.
3. **Lifecycle.** Agents are provisioned and *deprovisioned*; identities removed upstream are deactivated downstream.
4. **Runtime authorization.** Beyond identity, every consequential action is authorized in real time against policy and context.
5. **Delegation bounds.** An agent acting for a user can never exceed that user's permissions.
6. **Tamper-evident audit.** Every decision is recorded in an append-only, hash-chained log.

---

## Identity is necessary, not sufficient

This is the crucial distinction. Issuing an agent identity answers *who is this?* It does not answer *what may this agent do, on whose behalf, right now?* That second question — authorization — is where the actual risk lives, and it's the gap most NHI and identity tools leave open. The right architecture pairs an identity provider (to issue and track agent identities) with an authorization control plane (to govern what those identities are allowed to do at runtime).

## How Kynara fits

[Kynara](https://kynaraai.com) is the authorization side of that pairing. It **syncs agent identities from your IdP** (e.g. Okta), so the agents you govern stay in lockstep with your source of truth — and then it enforces what they can actually do: RBAC + ABAC policies evaluated per action, a non-escalation guarantee so an agent never exceeds its dispatching user, human approval for high-risk actions, MCP tool-call authorization, and a SHA-256 hash-chained audit log. Your IdP owns identity; Kynara owns authorization, containment, and the evidence trail.

Non-human identity isn't just a bigger version of human IAM. For AI agents, it's a new problem — and the teams that get ahead of it will be the ones who treat *authorization*, not just identity, as the control point.

*See how Kynara governs agent identities and actions — [book a demo](https://kynaraai.com) or read about [the AI agent permission problem](/blog/ai-agent-permission-problem).*
