"""LlamaIndex integration: gate FunctionTool calls through Kynara.

LlamaIndex agents use ``FunctionTool`` objects.  The cleanest integration
wraps the tool's ``fn`` at construction time so every call is gated without
modifying the tool implementation itself.

This example creates a ReActAgent with two tools (read_file, write_file) and
enforces Kynara policy before each tool execution.

Run:
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_llamaindex \\
    OPENAI_API_KEY=... \\
    python sdk/examples/llamaindex_agent.py
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable

from llama_index.core.agent import ReActAgent                          # type: ignore
from llama_index.core.tools import FunctionTool                        # type: ignore
from llama_index.llms.openai import OpenAI                             # type: ignore

from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired      # type: ignore

kynara = Kynara.from_env()
AGENT_ID = os.environ["KYNARA_AGENT_ID"]


# ---------------------------------------------------------------------------
# Kynara wrapper for LlamaIndex FunctionTools
# ---------------------------------------------------------------------------

def kynara_tool(
    fn: Callable[..., Any],
    action: str,
    resource_factory: Callable[..., dict] | None = None,
    **tool_kwargs: Any,
) -> FunctionTool:
    """Wrap a plain function in a Kynara-gated LlamaIndex FunctionTool.

    Args:
        fn: The underlying function to call if Kynara allows it.
        action: The Kynara action string, e.g. ``"file:read"``.
        resource_factory: Optional callable that receives the same kwargs as
            ``fn`` and returns the Kynara resource dict.  Defaults to
            ``{"fn": fn.__name__, **kwargs}``.
        **tool_kwargs: Passed through to ``FunctionTool.from_defaults``.
    """

    @functools.wraps(fn)
    def guarded(**kwargs: Any) -> str:
        resource = resource_factory(**kwargs) if resource_factory else {"fn": fn.__name__, **kwargs}
        try:
            kynara.enforce(
                subject=("agent", AGENT_ID),
                action=action,
                resource=resource,
                context={"framework": "llamaindex"},
            )
        except PermissionDenied as e:
            return f"[KYNARA DENIED] {e.decision.reason}"
        except ApprovalRequired as e:
            return f"[KYNARA APPROVAL REQUIRED] Visit {e.decision.approval_url} to approve"
        return fn(**kwargs)

    return FunctionTool.from_defaults(fn=guarded, **tool_kwargs)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    """Read the contents of a file."""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {path}"


def _write_file(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"Written {len(content)} bytes to {path}"


read_tool = kynara_tool(
    _read_file,
    action="file:read",
    resource_factory=lambda path: {"path": path},
    name="read_file",
    description="Read the contents of a local file.",
)

write_tool = kynara_tool(
    _write_file,
    action="file:write",
    resource_factory=lambda path, content="": {"path": path},
    name="write_file",
    description="Write content to a local file.",
)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

llm = OpenAI(model="gpt-4o-mini", temperature=0)
agent = ReActAgent.from_tools([read_tool, write_tool], llm=llm, verbose=True)


if __name__ == "__main__":
    response = agent.chat("Read the file /tmp/notes.txt and write a summary to /tmp/summary.txt")
    print(f"\nAgent response: {response}")
