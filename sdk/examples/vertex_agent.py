"""Google Vertex AI Agents integration: gate function calls through Kynara.

Vertex AI Agents (formerly Dialogflow CX / Agent Builder) support
``Function Calling`` for Gemini models, which is structurally identical
to OpenAI's tool_calls pattern.  The integration point is the function
dispatch loop: before executing any function returned by the model,
check Kynara.

This example uses the ``google-cloud-aiplatform`` SDK with a Gemini model
and demonstrates Kynara enforcement at the function dispatch layer.

Run:
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_vertex \\
    GOOGLE_CLOUD_PROJECT=my-project \\
    python sdk/examples/vertex_agent.py
"""
from __future__ import annotations

import json
import os
from typing import Any

import vertexai                                                         # type: ignore
from vertexai.generative_models import (                               # type: ignore
    FunctionDeclaration,
    GenerativeModel,
    Part,
    Tool,
)

from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired      # type: ignore

kynara = Kynara.from_env()
AGENT_ID = os.environ["KYNARA_AGENT_ID"]

# Initialise Vertex AI
vertexai.init(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
)


# ---------------------------------------------------------------------------
# Tool definitions (Vertex function declarations)
# ---------------------------------------------------------------------------

get_bigquery_data = FunctionDeclaration(
    name="get_bigquery_data",
    description="Query a BigQuery table and return results as JSON.",
    parameters={
        "type": "object",
        "properties": {
            "dataset": {"type": "string", "description": "BigQuery dataset ID"},
            "table": {"type": "string", "description": "Table name"},
            "limit": {"type": "integer", "description": "Row limit", "default": 100},
        },
        "required": ["dataset", "table"],
    },
)

send_pubsub_message = FunctionDeclaration(
    name="send_pubsub_message",
    description="Publish a message to a Pub/Sub topic.",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Pub/Sub topic name"},
            "message": {"type": "string", "description": "Message payload"},
        },
        "required": ["topic", "message"],
    },
)

vertex_tools = Tool(function_declarations=[get_bigquery_data, send_pubsub_message])


# ---------------------------------------------------------------------------
# Kynara-aware function dispatcher
# ---------------------------------------------------------------------------

def _execute_function(name: str, args: dict) -> str:
    """Execute a Vertex function call after Kynara enforcement."""
    try:
        kynara.enforce(
            subject=("agent", AGENT_ID),
            action=f"vertex:{name}",
            resource={"function": name, **args},
            context={"framework": "vertex_ai"},
        )
    except PermissionDenied as e:
        return json.dumps({"error": "denied", "reason": e.decision.reason})
    except ApprovalRequired as e:
        return json.dumps({"error": "approval_required", "approval_url": e.decision.approval_url})

    # Dispatch to real implementations
    if name == "get_bigquery_data":
        return json.dumps({
            "rows": [{"id": 1, "name": "mock_row"}],
            "total": 1,
            "dataset": args["dataset"],
            "table": args["table"],
        })
    if name == "send_pubsub_message":
        return json.dumps({"message_id": "mock-msg-001", "topic": args["topic"]})
    return json.dumps({"error": f"unknown function: {name}"})


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_agent(prompt: str, max_turns: int = 5) -> str:
    """Run a Gemini agent with Kynara enforcement on every function call."""
    model = GenerativeModel("gemini-1.5-flash", tools=[vertex_tools])
    messages = [{"role": "user", "parts": [{"text": prompt}]}]

    for turn in range(max_turns):
        response = model.generate_content(messages)
        candidate = response.candidates[0]
        content = candidate.content

        # Check for function calls
        function_calls = [
            part.function_call
            for part in content.parts
            if hasattr(part, "function_call") and part.function_call
        ]

        if not function_calls:
            # No more tool calls — return the final text response
            return "".join(
                part.text for part in content.parts if hasattr(part, "text")
            )

        # Execute all function calls (with Kynara gate)
        function_responses = []
        for fc in function_calls:
            result = _execute_function(fc.name, dict(fc.args))
            function_responses.append(
                Part.from_function_response(name=fc.name, response={"content": result})
            )

        # Append model turn + function responses to the conversation
        messages.append({"role": "model", "parts": content.parts})
        messages.append({"role": "user", "parts": function_responses})

    return "Max turns reached without a final answer."


if __name__ == "__main__":
    answer = run_agent(
        "Get the last 10 rows from the analytics.events table "
        "and publish a summary to the reports Pub/Sub topic."
    )
    print(f"\nFinal answer:\n{answer}")
