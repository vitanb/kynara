# The Principle of Least Privilege for AI Agents

### The oldest rule in security is suddenly the hardest to follow — because agents are over-privileged by default.

Least privilege — give every actor the minimum access it needs, and no more — has been a security cornerstone for fifty years. It's also the principle AI agents violate most casually. An agent gets handed broad credentials and a generous toolbelt "so it can handle whatever comes up," and just like that, a single prompt-injectable, autonomous system has standing access to far more than it will ever legitimately use.

Applying least privilege to agents isn't optional anymore. Here's what it means in practice and how to actually enforce it.

---

## What least privilege means for an AI agent

For agents, least privilege has four dimensions that go beyond "give it a narrow role":

- **Minimal scope.** The agent can call only the specific tools and access only the specific resources its job requires.
- **Bounded by delegation.** When acting for a user, the agent's effective permissions are the *intersection* of its own grants and that user's grants — never more.
- **Context-bound.** Access is conditioned on runtime context: time, environment, region, amount, sensitivity of the specific record.
- **Time-boxed.** Elevated access, when truly needed, is granted just-in-time and expires automatically.

A static "this agent can read CRM" grant satisfies none of these well.

---

## Why agents are over-privileged by default

- **Broad credentials.** Agents are wired to upstream systems with powerful service tokens, because that's the path of least resistance.
- **"Just in case" tools.** Every tool the team might want is registered up front, expanding the blast radius.
- **Standing grants.** Permissions are set once at deploy time and never revisited, so they only ever accumulate.
- **No per-action check.** Even a well-scoped role does nothing if there's no enforcement deciding each individual action.

The result: the gap between what an agent *can* do and what it *should* do is enormous — and that gap is exactly the attack surface.

---

## How to enforce least privilege for agents

1. **Scope tools to roles.** Map each tool to a capability scope and grant agents only the scopes they need. Deny by default.
2. **Enforce non-escalation.** Make the agent's authority the intersection of its roles and the dispatching user's roles, so it can never exceed the human behind it.
3. **Authorize at runtime, per action.** Check every consequential call against policy *and* context — not just at deploy time. Static configuration is not enforcement.
4. **Least-privilege discovery.** Don't even advertise tools an agent can't use. If you front MCP servers with a gateway, hide disallowed tools so the agent never sees them.
5. **Just-in-time elevation.** For genuine break-glass cases, grant a scoped, time-boxed elevation with a justification — recorded in the audit trail — that expires on its own.
6. **Fail closed.** If the policy engine is unreachable, deny. An agent should lose access on failure, not gain it.

---

## Least privilege is a runtime property, not a config setting

The most common mistake is treating least privilege as something you set up once. For agents, it's a *runtime* property: the same agent might legitimately read a record at 10am from an allowed region and be denied the identical call at 2am from elsewhere. Real least privilege means evaluating each action against policy and live context at the moment it happens — and recording the decision.

## How Kynara enforces it

[Kynara](https://kynaraai.com) is built around least privilege for agents. Tools map to scopes; agents get only the scopes they need; every action is evaluated per-call against RBAC + ABAC policies and runtime context, returning `allow`, `deny`, or `require_approval`. The **non-escalation guarantee** is enforced automatically, **JIT grants** cover time-boxed break-glass elevation, the **MCP Gateway** hides disallowed tools (least-privilege discovery), and everything is fail-closed by default and recorded in a tamper-evident audit log.

Least privilege is the cheapest, highest-leverage control you can apply to an AI agent. For autonomous systems that can be manipulated, it's also the difference between a contained incident and an unbounded one.

*See how Kynara shrinks the gap between what your agents can do and what they should — [book a demo](https://kynaraai.com), or read about [securing MCP servers](/blog/securing-mcp-servers).*
