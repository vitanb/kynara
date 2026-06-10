# How to Secure MCP Servers: Authorization, Least Privilege, and Audit for AI Agent Tools

### MCP made it trivial for agents to call your tools. Securing those calls is now your problem.

The Model Context Protocol (MCP) has become the default way AI agents reach the real world. Point an agent at an MCP server and it can suddenly query your database, file tickets, send email, deploy code, or move money — through a clean, standard interface. That standardization is exactly why MCP took off. It's also why MCP is now one of the most important — and least governed — attack surfaces in the AI stack.

Here's the uncomfortable truth: **MCP has no built-in answer to the question that matters most — *which agent is allowed to call which tool, on whose behalf, under what conditions?*** If an agent can reach a tool, it can call it. Let's look at why that's dangerous and how to actually secure it.

---

## The MCP security gaps

**1. Over-broad tool access.** Most MCP deployments expose every tool on the server to every connected agent. A read-only assistant ends up with `delete_record` and `send_email` in its toolbelt "just in case." That violates least privilege by default.

**2. No per-agent authorization.** MCP's spec covers *authentication* (often OAuth) — proving *who is connecting*. It does not cover fine-grained *authorization* — deciding whether *this specific agent*, acting for *this specific user*, may call *this specific tool* with *these arguments* right now. Those are different problems, and the second one is where the risk lives.

**3. Prompt injection turns tools into weapons.** An agent's tool calls are driven by an LLM, and the LLM is manipulable. A malicious instruction buried in a web page or document can convince the model to call a destructive tool. If nothing sits between the model's decision and the tool's execution, the injection succeeds.

**4. The confused-deputy problem.** An agent often holds broad credentials to the upstream system. Without per-action checks, any user who can talk to the agent can effectively borrow those credentials — escalating their own access through the agent.

**5. No audit trail.** When something goes wrong, "the agent did it" isn't an answer. You need to know which agent, which tool, which arguments, which user, and whether the record can be trusted.

---

## Why "just add OAuth" isn't enough

OAuth on your MCP server is necessary but not sufficient. It answers *is this caller authenticated?* — not *should this action be allowed?* You can have a perfectly authenticated agent that should still be denied a specific tool call because it's outside business hours, from the wrong region, on a restricted record, or simply beyond what its role permits. Authentication is the front door; authorization is what happens inside every room.

---

## The pattern that works: a policy gateway in front of MCP

The architectural consensus in 2026 has converged on one idea: **enforce at the gateway, not in each tool.** Put a policy enforcement point between agents and your MCP servers so that *every* tool call is checked consistently, with a unified audit trail and no per-tool rewrites.

A well-secured MCP setup does five things:

1. **Per-call authorization.** Every `tools/call` is evaluated against policy and returns `allow`, `deny`, or `require_approval` — based on the agent, the user it acts for, the tool, the arguments, and runtime context.
2. **Least-privilege discovery.** Agents only *see* the tools they're permitted to use. A tool an agent can't call is never even advertised to it, shrinking the attack surface and reducing prompt-injection options.
3. **Human-in-the-loop for high-risk tools.** Destructive or sensitive tools (refunds, deletes, production changes) can require a human approval before they run.
4. **A tamper-evident audit log.** Every decision is recorded in an append-only, hash-chained log so you can prove exactly what happened and that the record wasn't altered.
5. **Enforcement outside the LLM's trust boundary.** The policy layer evaluates structured requests — agent, tool, arguments, context — not natural language. A prompt injection inside the model can't change what the gateway receives or how it decides.

---

## How Kynara secures MCP

The [Kynara MCP Gateway](https://kynaraai.com/docs) is a drop-in proxy you place in front of any MCP server. Agents swap one URL — no agent-side code changes — and from then on:

- Every tool call is authorized per-agent against your RBAC + ABAC policies.
- Each upstream tool is mapped to a Kynara scope (e.g. `mcp.crm.contacts.read`), so the same policy engine that governs the rest of your agents governs MCP tool calls too.
- Agents see only the tools they're allowed to call (least-privilege discovery); a tool pinned to deny can't be invoked even by name.
- High-risk tools can route to human approval.
- Every decision lands in Kynara's SHA-256 hash-chained audit log.

Because mapped scopes flow through the same control plane, you also inherit the **non-escalation guarantee** — an agent can never exceed the permissions of the user who dispatched it — and a compliance-ready audit trail, for free.

---

## An MCP security checklist

- [ ] Authenticate every MCP connection (OAuth or signed keys).
- [ ] Authorize every tool call per-agent, per-user, with context — not just at connect time.
- [ ] Default to least privilege; only expose tools an agent actually needs.
- [ ] Require human approval for destructive or high-value tools.
- [ ] Keep a tamper-evident, append-only audit log of every decision.
- [ ] Enforce outside the LLM so prompt injection can't bypass it.
- [ ] Centralize it at a gateway so policy is consistent across every MCP server.

MCP gave your agents reach. A policy gateway gives you control. You want both.

*See how the [Kynara MCP Gateway](https://kynaraai.com) authorizes every tool call, or try the [sandbox](https://kynaraai.com/sandbox).*
