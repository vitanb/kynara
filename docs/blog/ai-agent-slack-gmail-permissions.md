# Stop Handing Your AI Agent the Token: Control Before Capability, Not After

### When your agent can post to Slack or send Gmail, an access token isn't a permission model. Here's how to actually constrain it — at the right layer.

If you've wired an AI agent up to Slack or Gmail, you've probably felt this: you hand it an OAuth token, and now it can do *anything within that scope.* It can post to the wrong channel, email the wrong person, read more than it should. As one developer put it recently: **"once the agent has access, it has too much freedom."**

The common fixes work — but they all share a flaw. They start from broad access and try to constrain it *after* the fact. There's a better mental model: **control the capability before it's ever exposed.** Let's break down both.

---

## Why the token is the wrong layer

An OAuth scope like `gmail.send` or a Slack bot token answers "is this app allowed to use this API?" It says nothing about *which message, to which channel, to which recipient, right now.* That granularity — the part that actually matters for safety — lives one layer up, between the agent's decision to call a tool and the tool actually executing.

So the first rule is simple: **don't hand the agent a raw token and hope.** Put a control point between the tool call and the API.

---

## What teams do today (and why it's still reactive)

The battle-tested patterns look like this:

- **Validate intent before execution.** Route every tool call through middleware that checks it first — e.g., "send Slack message" only passes if the destination channel is on an allowlist.
- **Scope tightly.** Use `gmail.send` only, never `gmail.modify` or `gmail.readonly`. (Most devs grab the broad scope for convenience and never revisit it.)
- **Log the full payload.** Record the entire tool-call payload — not just the function name — *before* execution. You catch over-reach fast.
- **Add a confirmation gate.** Require async human approval for destructive or external-facing actions.
- **Use capability tokens.** Short-lived, narrow-scope credentials minted per task instead of one persistent token.

These are good. But notice the shape: *the agent already has broad access, and we're inspecting and constraining it on the way out.* It works, but you're forever patching around the same over-privileged starting point.

---

## The shift: control before capability is exposed

The better question is the one that thread eventually arrived at: *what if the control happened before the capability was even available, instead of validating it after?*

That's two complementary layers:

### Layer 1 — Don't expose what the agent can't use (least-privilege discovery)

The strongest control isn't denying a bad call — it's making the bad call un-callable. If an agent isn't allowed to use a tool, **don't even advertise the tool to it.** The agent's toolbelt is derived from policy, per agent, so a capability it shouldn't have simply isn't there. That shrinks the attack surface *and* removes options a prompt-injected model could try to exploit.

### Layer 2 — Authorize the intent, at the argument level, before execution

For the tools an agent *can* use, decide each call against policy and the actual arguments — the Slack channel, the email recipient, the amount — and return `allow`, `deny`, or `require_approval` before any side effect runs.

This is where argument-level policy matters. A Slack channel allowlist is just:

```json
{ "op": "in", "args": ["ctx.resource.attrs.channel", ["C0123ALLOWED", "C0456ALLOWED"]] }
```

Gmail "internal recipients only" is:

```json
{ "op": "ends_with", "args": ["ctx.resource.attrs.recipient", "@yourcompany.com"] }
```

And "anything to an external recipient needs a human" is:

```json
{ "op": "not",
  "args": [ { "op": "ends_with", "args": ["ctx.resource.attrs.recipient", "@yourcompany.com"] } ] }
```

→ `require_approval`. Now the agent can email teammates freely, but the moment it tries to message someone outside the company, a human gets a review request with the full payload before anything is sent.

---

## The part that makes it trustworthy

Two more pieces turn this from "nice middleware" into something you can stand behind:

- **Enforce outside the model.** The policy check evaluates structured data — agent, tool, arguments, context — not the prompt. A prompt injection can't argue its way past it. The model can decide to email the whole company; the policy still says no.
- **Keep a tamper-evident log.** Record every decision and the full payload in an append-only, hash-chained log. That's how you catch the "CC'd a distribution list 23% of the time" problems — and prove what happened later.

---

## How Kynara does this

[Kynara](https://kynaraai.com) is built around exactly this model:

- **Least-privilege discovery** — its MCP Gateway only exposes the tools an agent is allowed to call; disallowed tools are never advertised.
- **Argument-level policies** — conditions read tool arguments via `ctx.resource.attrs.*`, with operators like `in`, `ends_with`, and `starts_with`. The Slack and Gmail policies above are built-in templates you can load in one click.
- **Human-in-the-loop** — any rule can return `require_approval`, pausing the action for review.
- **Non-escalation** — an agent can never exceed the permissions of the user who dispatched it.
- **Tamper-evident audit** — every decision lands in a SHA-256 hash-chained log.

You still build your agent however you like — LangChain, CrewAI, an MCP server. Kynara decides what it's allowed to do, before it does it.

---

## The takeaway

A token gives your agent reach. It doesn't give you control. The fix isn't a smarter "are you sure?" check bolted on after the agent already has the keys — it's flipping the model so capability is granted by policy, exposed only when allowed, and authorized at the argument level before anything happens.

Control before capability. Not after.

*Want the Slack/Gmail policies ready to load? See the [Kynara docs](https://kynaraai.com/docs) or try the [sandbox](https://kynaraai.com/sandbox).*
