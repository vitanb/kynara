# Adding Permissions to LangChain Agents: A Practical Guide

### LangChain makes tool-calling effortless. Deciding which tools an agent may actually use is still on you.

LangChain (and LangGraph) turned "give an LLM some tools and let it act" into a few lines of code. That's the appeal — and the problem. By default, a LangChain agent will call whichever tool the model decides to call, with whatever arguments the model produces. There's no built-in notion of *permissions*: no concept of which agent may call which tool, on whose behalf, or under what conditions.

For a demo, that's fine. For an agent that can send email, modify records, or move money, it's a liability. Here's how to add real permissions to LangChain agents — the pattern, the code, and the pitfalls.

---

## The core idea: gate tools at the boundary

The right place to enforce permissions is **at the tool boundary** — between the model's decision to call a tool and the tool actually executing. You want a check that runs *before* any side effect and can:

- `allow` the call to proceed,
- `deny` it (raise an error the agent sees, so the side effect never happens),
- or `require_approval` (pause and surface an approval request to a human).

There are two clean ways to do this in LangChain: a **callback handler** that intercepts every tool start, or a **wrapper/decorator** around each tool.

---

## Pattern 1: a callback handler

A callback handler hooks `on_tool_start` for *every* tool the agent invokes — one place to enforce policy across all tools:

```python
from langchain.agents import AgentExecutor
from kynara_sdk.langchain import KynaraCallbackHandler

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[KynaraCallbackHandler(agent_id=AGENT_ID)],
)
```

Before any tool runs, the handler asks the decision engine whether this agent may perform this action with these arguments. A `deny` stops the call; a `require_approval` pauses it.

## Pattern 2: wrap individual tools

When you want per-tool control, guard the tool function itself:

```python
from langchain.tools import tool
from kynara_sdk import permission_required

@tool
@permission_required("crm.contacts.read", resource_arg="contact_id")
def get_contact(contact_id: str) -> str:
    """Retrieve a CRM contact by id."""
    return crm.fetch(contact_id)
```

If the decision is `deny`, `permission_required` raises before the function body runs — the CRM is never queried. The agent receives a clear, structured error instead of a side effect.

---

## The same pattern works beyond LangChain

This boundary-enforcement approach isn't LangChain-specific. The same decision check slots into **LangGraph** nodes, **AutoGen** tool execution, **CrewAI** tasks, and plain Python or TypeScript tool functions. Pick the integration point your framework gives you (callback, middleware, decorator) and put the check there.

---

## Why this belongs outside the LLM

A critical detail: the permission check must live *outside* the model's reasoning. The decision engine evaluates structured data — the agent, the action, the arguments, the context — not the natural-language prompt. That means a prompt injection inside the LLM can't talk its way past the check. The model can decide to call `delete_all_records`; the policy layer still says no.

---

## Best practices

- **Least privilege.** Only register the tools an agent actually needs, and scope each to a role.
- **Use context.** Make decisions depend on runtime context (time, user, environment, amount), not just the tool name.
- **Approvals for high-risk tools.** Route destructive or high-value calls through human approval.
- **Audit everything.** Record every decision in a tamper-evident log so you can prove what happened.
- **Fail closed.** If the policy engine is unreachable, deny by default.

---

## How Kynara does it

[Kynara](https://kynaraai.com) ships a `KynaraCallbackHandler` for LangChain/LangGraph and a `permission_required` decorator for individual tools, plus integrations for AutoGen, CrewAI, OpenAI, and Anthropic — and Express middleware on the TypeScript side. Under the hood, every check runs against your RBAC + ABAC policies with the non-escalation guarantee, optional human approval, and a SHA-256 hash-chained audit log. You keep building agents in LangChain; Kynara decides what they're allowed to do.

*Try it in the [sandbox](https://kynaraai.com/sandbox), or read more on [agent least privilege](/blog/agent-least-privilege).*
