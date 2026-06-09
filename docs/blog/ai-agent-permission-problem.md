# The AI Agent Permission Problem — and How to Solve It

### Your AI agents can now call real APIs. Who decides what they're allowed to do?

For the last two years, the hard part of building with AI was getting the model to *do* things. That problem is largely solved. Agents now read your databases, file tickets, send emails, move money, and restart production services — autonomously, in a loop, sometimes thousands of times a day.

Which means the hard part is no longer capability. It's **control**.

The moment an agent can take a real action, you inherit a question that no agent framework answers for you: *what is this agent actually allowed to do — on whose behalf, under what conditions, right now — and can you prove what it did afterward?*

This is the AI agent permission problem. Here's why it's harder than it looks, why the tools you already have don't solve it, and what a real solution looks like.

---

## Why this is different from normal access control

It's tempting to assume this is a solved problem. We've had IAM for decades. AWS IAM, Okta, OPA, Casbin — surely one of these covers it?

They cover *part* of it. But the agent trust model adds dimensions traditional access control was never designed for:

**1. Delegation.** An agent rarely acts as itself. It acts *on behalf of a user*. If Alice asks her assistant agent to "clean up my calendar," the agent should be able to do what Alice can do — and nothing more. Traditional IAM models a principal acting as itself. It has no native concept of "Agent A, acting for User B, bounded by the intersection of both their permissions."

**2. Runtime context.** A human's permissions are mostly static. An agent's *should* depend on the moment: the time of day, the originating IP, the environment, the dollar amount, the sensitivity of the specific record. "Can read CRM contacts" is too coarse. "Can read *this* contact, during business hours, from an allowed region, when not flagged as restricted" is the real question.

**3. Non-determinism.** A compromised or prompt-injected agent doesn't behave like a buggy script. It improvises. It will try tool calls you never anticipated. Your controls have to assume the agent itself is untrusted.

**4. Auditability that satisfies a regulator, not just a developer.** When something goes wrong — and with autonomous systems, something will — you need to replay exactly what happened: which agent, which action, which policy matched, who approved it, and proof the record wasn't altered after the fact. "We have logs somewhere" doesn't pass a compliance review.

Standard IAM answers *"does this principal have permission for this action?"* The agent question is richer: *"does this agent, acting on behalf of this user, under these runtime conditions, using this specific tool, have permission at this instant — and is the answer provably recorded?"*

---

## Where existing tools fall short

- **Agent frameworks (LangChain, CrewAI, AutoGen, the MCP ecosystem)** give you tools and orchestration. They have no opinion on authorization. A tool is a tool; if the model decides to call it, it runs.
- **Policy engines (OPA, Cerbos, Casbin)** are excellent at *evaluating* a policy against data you hand them. But they're libraries, not control planes. You still have to supply the identities, the delegation model, the approval workflows, the tamper-evident audit, and the enforcement at the tool boundary. That's most of the work.
- **Identity providers (Okta, Entra, Auth0)** are increasingly issuing first-class *agent identities* — which is genuinely useful. But knowing *who* an agent is doesn't tell you *what it may do*. Verifying identity and authorizing a specific action are two different problems. The industry now openly calls the second one "the authorization gap."

So teams end up stitching these together by hand: a bit of OPA here, a homegrown approval queue there, some logging, a brittle "are you sure?" check before the dangerous tools. It works until it doesn't — and it never produces the clean audit trail you actually need.

---

## What a control plane for AI agents needs

A real solution isn't a library you wire in. It's a control plane that sits **outside the agent's trust boundary** and owns five things:

1. **A decision API.** Before any side effect, the agent (or the layer in front of it) asks one question — *can I do this?* — and gets back `allow`, `deny`, or `require_approval`. The engine evaluates RBAC + ABAC rules against the subject, the action, the resource, and live context. Enforcement happens at the tool boundary, so a `deny` means the side effect never runs.

2. **Non-escalation by construction.** When an agent acts for a user, its effective permissions are the *intersection* of the agent's roles and the user's roles. An agent can never acquire more authority than the human who dispatched it — no matter how permissive its own policy is. This single invariant eliminates a whole class of privilege-escalation-via-impersonation.

3. **Human-in-the-loop as a first-class outcome.** Some actions shouldn't be autonomous. When a policy returns `require_approval`, the agent pauses and a human reviews the request *with full context* — which agent, which action, which resource, the risk score — and approves or rejects. The agent resumes or aborts. This is the difference between "the AI did something alarming" and "the AI asked, and a human said no."

4. **A tamper-evident audit trail.** Every decision is appended to a hash-chained log (SHA-256 is the de-facto standard, and it's what the EU AI Act's Article 12 logging obligations effectively require). If any past record is altered, the chain breaks and it's detectable. That's the difference between logs and *evidence*.

5. **Enforcement that meets agents where they live.** SDK decorators for Python, middleware for TypeScript, callbacks for LangChain/AutoGen/CrewAI — and, increasingly, a gateway in front of MCP servers so that *every tool call* is authorized per-agent, with agents only seeing the tools they're allowed to use.

---

## How Kynara solves it

[Kynara](https://kynaraai.com) is a permission control plane built specifically for AI agents. The core is exactly the decision API above:

```python
from kynara_sdk import permission_required

@permission_required("payments.refund.issue", resource_arg="refund_id")
def issue_refund(refund_id: str, amount_cents: int):
    return stripe.refund(refund_id, amount_cents)
```

If the decision is `deny`, the decorator raises `PermissionDenied` **before the function body runs** — the refund never happens. If it's `require_approval`, the call pauses and surfaces an approval URL for a human to resolve.

Under that one call, Kynara provides the rest of the control plane:

- **RBAC + ABAC** evaluated against runtime context (time, IP, user role, resource attributes), returning `allow` / `deny` / `require_approval`.
- **The non-escalation guarantee** across the agent→user delegation chain, enforced automatically.
- **Approval workflows** with a human review UI, risk scoring, and routing to Slack/Teams.
- **A SHA-256 hash-chained audit log** — tamper-evident by design, exportable for SOC 2, ISO 27001, and EU AI Act conformance.
- **An MCP authorization gateway** that fronts any Model Context Protocol server and authorizes every tool call per-agent, hiding tools an agent isn't permitted to use (least-privilege discovery).
- **Identity-provider sync** (e.g. Okta) so agent identities flow in from your existing IdP — Okta owns *identity*, Kynara owns *authorization*.

Crucially, Kynara sits *outside the model's trust boundary*. It evaluates structured requests — subject, action, resource, context — not natural language. A prompt injection inside the LLM can't change what Kynara receives or how it decides. The model can ask for anything; the control plane still says no.

---

## Getting started

You don't have to re-architect to adopt this. The fastest path is to wrap the handful of tools that actually have consequences — the ones that write data, move money, or touch production — and let everything else through:

1. Register your agents and define a few policies (allow business-hours CRM reads; require approval for refunds; deny anything from blocked regions).
2. Add the decorator/middleware to those high-consequence tools, or point your MCP clients at the Kynara gateway.
3. Watch the decisions flow into the audit log, and tune from there.

You can try the policy logic without writing any code in the [sandbox](https://kynaraai.com/sandbox), and the full guide is in the [docs](https://kynaraai.com/docs).

---

## The takeaway

Capability is no longer the bottleneck for AI agents — *governance* is. The teams that ship agents into real workflows safely won't be the ones with the cleverest prompts. They'll be the ones who can answer, at any moment and with proof: *what is this agent allowed to do, on whose behalf, and what did it actually do?*

That's the AI agent permission problem. Solving it is what Kynara is for.

*Want to see it on your own stack? [Book a demo](https://kynaraai.com) or explore the [sandbox](https://kynaraai.com/sandbox).*
