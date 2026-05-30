"""Microsoft Semantic Kernel integration: gate kernel function invocations through Kynara.

Semantic Kernel (SK) uses ``KernelPlugin`` objects containing ``KernelFunction``
instances.  The cleanest integration is a custom ``FunctionInvocationFilter``
— SK's official middleware hook that fires before and after every function call.
This keeps Kynara logic in one place regardless of how many plugins are loaded.

Run:
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_sk \\
    OPENAI_API_KEY=... \\
    python sdk/examples/semantic_kernel_agent.py
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

import semantic_kernel as sk                                            # type: ignore
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion # type: ignore
from semantic_kernel.filters.functions.function_invocation_context import (  # type: ignore
    FunctionInvocationContext,
)
from semantic_kernel.functions import kernel_function                   # type: ignore

from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired      # type: ignore

kynara = Kynara.from_env()
AGENT_ID = os.environ["KYNARA_AGENT_ID"]


# ---------------------------------------------------------------------------
# Kynara invocation filter
# ---------------------------------------------------------------------------

class KynaraFilter:
    """Semantic Kernel FunctionInvocationFilter that enforces Kynara policy.

    Register with:
        kernel.add_filter("function_invocation", KynaraFilter())
    """

    async def on_function_invocation(
        self,
        context: FunctionInvocationContext,
        next: Callable,
    ) -> None:
        plugin_name = context.function.plugin_name or "unknown"
        fn_name = context.function.name
        args = {k: str(v) for k, v in (context.arguments or {}).items()}

        try:
            kynara.enforce(
                subject=("agent", AGENT_ID),
                action=f"{plugin_name}:{fn_name}",
                resource={"plugin": plugin_name, "function": fn_name, **args},
                context={"framework": "semantic_kernel"},
            )
        except PermissionDenied as e:
            # Override the result with a denial message rather than raising —
            # SK handles the string result gracefully in the chat loop.
            context.result = sk.FunctionResult(  # type: ignore
                function=context.function,
                value=f"[KYNARA DENIED] {e.decision.reason}",
            )
            return
        except ApprovalRequired as e:
            context.result = sk.FunctionResult(  # type: ignore
                function=context.function,
                value=f"[KYNARA APPROVAL REQUIRED] {e.decision.approval_url}",
            )
            return

        # Allow: continue with the actual function execution
        await next(context)


# ---------------------------------------------------------------------------
# Sample plugins
# ---------------------------------------------------------------------------

class FilePlugin:
    @kernel_function(name="read_file", description="Read contents of a local file")
    def read_file(self, path: str) -> str:
        try:
            with open(path) as f:
                return f.read()
        except FileNotFoundError:
            return f"File not found: {path}"

    @kernel_function(name="write_file", description="Write text content to a local file")
    def write_file(self, path: str, content: str) -> str:
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"


class EmailPlugin:
    @kernel_function(name="send_email", description="Send an email to a recipient")
    def send_email(self, to: str, subject: str, body: str) -> str:
        # Real implementation would call an email API
        return f"[mock] Email sent to {to} — subject: {subject}"


# ---------------------------------------------------------------------------
# Kernel setup and chat loop
# ---------------------------------------------------------------------------

async def main() -> None:
    kernel = sk.Kernel()

    # Register AI service
    kernel.add_service(
        OpenAIChatCompletion(
            service_id="gpt4o-mini",
            ai_model_id="gpt-4o-mini",
        )
    )

    # Register Kynara filter — fires before every kernel function
    kernel.add_filter("function_invocation", KynaraFilter())

    # Register plugins
    kernel.add_plugin(FilePlugin(), plugin_name="FilePlugin")
    kernel.add_plugin(EmailPlugin(), plugin_name="EmailPlugin")

    # Simple single-turn invocation
    result = await kernel.invoke(
        plugin_name="FilePlugin",
        function_name="read_file",
        path="/tmp/report.txt",
    )
    print(f"read_file result: {result}")

    result = await kernel.invoke(
        plugin_name="EmailPlugin",
        function_name="send_email",
        to="boss@example.com",
        subject="Daily Report",
        body="Here is today's report...",
    )
    print(f"send_email result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
