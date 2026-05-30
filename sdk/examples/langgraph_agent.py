"""LangGraph integration: gate every tool node through Kynara.

LangGraph agents are directed graphs where tool calls happen in dedicated
nodes.  The cleanest integration point is a ``before_tool`` pre-processor
added via ``graph.add_node`` or by wrapping the ``ToolNode`` that LangGraph
provides out of the box.

This example builds a simple ReAct-style graph with two tools (web_search and
send_email) and gates both through Kynara before execution.

Run:
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_langgraph \\
    OPENAI_API_KEY=... \\
    python sdk/examples/langgraph_agent.py
"""
from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage          # type: ignore
from langchain_core.tools import tool                                   # type: ignore
from langchain_openai import ChatOpenAI                                 # type: ignore
from langgraph.graph import StateGraph, END                             # type: ignore
from langgraph.prebuilt import ToolNode                                 # type: ignore

from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired      # type: ignore

kynara = Kynara.from_env()
AGENT_ID = os.environ["KYNARA_AGENT_ID"]


# ---------------------------------------------------------------------------
# Kynara-aware ToolNode wrapper
# ---------------------------------------------------------------------------

class KynaraToolNode(ToolNode):
    """Subclass of LangGraph's ToolNode that checks Kynara before every tool call.

    LangGraph's ToolNode iterates over tool calls in the last AI message and
    invokes each tool.  We intercept at that boundary so the check is framework-
    level rather than scattered across each individual tool.
    """

    def _run_one(self, call: dict, config: dict) -> ToolMessage:  # type: ignore
        tool_name = call["name"]
        tool_args = call.get("args", {})

        try:
            kynara.enforce(
                subject=("agent", AGENT_ID),
                action=f"tool:{tool_name}",
                resource={"tool": tool_name, "args": tool_args},
                context={"framework": "langgraph"},
            )
        except PermissionDenied as e:
            return ToolMessage(
                content=f"[KYNARA DENIED] {e.decision.reason}",
                tool_call_id=call["id"],
            )
        except ApprovalRequired as e:
            return ToolMessage(
                content=f"[KYNARA APPROVAL REQUIRED] {e.decision.approval_url}",
                tool_call_id=call["id"],
            )

        return super()._run_one(call, config)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def web_search(query: str) -> str:
    """Search the web for information."""
    # Real implementation would call a search API
    return f"[mock search results for: {query}]"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a recipient."""
    # Real implementation would call an email API
    return f"[mock: email sent to {to} — subject: {subject}]"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

tools = [web_search, send_email]
tool_node = KynaraToolNode(tools)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)


def call_llm(state: dict) -> dict:
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": messages + [response]}


def should_continue(state: dict) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


graph = StateGraph(dict)
graph.add_node("agent", call_llm)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")
app = graph.compile()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = app.invoke({
        "messages": [HumanMessage(content="Search for the latest AI news and email a summary to boss@example.com")]
    })
    for msg in result["messages"]:
        role = getattr(msg, "type", "unknown")
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        print(f"[{role}] {content[:200]}")
