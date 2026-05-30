"""AWS Bedrock Agents integration: gate action group invocations through Kynara.

AWS Bedrock Agents call Lambda functions (Action Groups) when they need to
take actions.  There are two integration points:

1. **Lambda handler level** — Kynara checks every action group invocation
   inside the Lambda function before it executes.  This is the most secure
   approach and works regardless of how the agent is deployed.

2. **Bedrock inline agent (boto3)** — When calling the agent via
   ``bedrock-agent-runtime.invoke_agent``, gate the call itself before
   sending it to Bedrock.

This file demonstrates both patterns.

Run Lambda locally (pattern 1):
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_bedrock \\
    python sdk/examples/bedrock_agent.py

Invoke via boto3 (pattern 2):
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_bedrock \\
    AWS_REGION=us-east-1 \\
    python sdk/examples/bedrock_agent.py --invoke
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired      # type: ignore

kynara = Kynara.from_env()
AGENT_ID = os.environ["KYNARA_AGENT_ID"]


# ---------------------------------------------------------------------------
# Pattern 1: Lambda action group handler with Kynara gate
# ---------------------------------------------------------------------------

def _format_response(action_group: str, function: str, result: str) -> dict:
    """Format a Bedrock action group response."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function,
            "functionResponse": {
                "responseBody": {"TEXT": {"body": result}}
            },
        },
    }


def bedrock_action_group_handler(event: dict, context: Any) -> dict:
    """Lambda handler for a Bedrock Agent action group.

    Kynara is checked before any action executes.  If denied, Bedrock
    receives an error response and the agent can decide how to proceed.
    """
    action_group = event.get("actionGroup", "")
    function = event.get("function", "")
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}

    # Gate the action through Kynara
    try:
        kynara.enforce(
            subject=("agent", AGENT_ID),
            action=f"{action_group}:{function}",
            resource={"action_group": action_group, "function": function, **parameters},
            context={"framework": "bedrock_agents", "invocation_id": event.get("invocationId")},
        )
    except PermissionDenied as e:
        return _format_response(
            action_group, function,
            f"Action denied by security policy: {e.decision.reason}"
        )
    except ApprovalRequired as e:
        return _format_response(
            action_group, function,
            f"Action requires approval. Approve at: {e.decision.approval_url}"
        )

    # Dispatch to the actual implementation
    result = _dispatch(action_group, function, parameters)
    return _format_response(action_group, function, result)


def _dispatch(action_group: str, function: str, params: dict) -> str:
    """Route to the real tool implementation."""
    if action_group == "DatabaseActions" and function == "query_database":
        return f"[mock] SELECT * FROM {params.get('table', 'unknown')} LIMIT 10"
    if action_group == "EmailActions" and function == "send_email":
        return f"[mock] Email sent to {params.get('to', 'unknown')}"
    return f"Unknown action: {action_group}.{function}"


# ---------------------------------------------------------------------------
# Pattern 2: Gate the Bedrock invoke_agent call itself
# ---------------------------------------------------------------------------

def invoke_bedrock_agent(
    agent_id: str,
    agent_alias_id: str,
    session_id: str,
    prompt: str,
) -> str:
    """Invoke a Bedrock Agent, gating the call through Kynara first."""
    try:
        kynara.enforce(
            subject=("agent", AGENT_ID),
            action="bedrock:invoke_agent",
            resource={"agent_id": agent_id, "agent_alias_id": agent_alias_id},
            context={"framework": "bedrock_agents", "session_id": session_id},
        )
    except PermissionDenied as e:
        return f"DENIED: {e.decision.reason}"
    except ApprovalRequired as e:
        return f"APPROVAL REQUIRED: {e.decision.approval_url}"

    import boto3
    client = boto3.client("bedrock-agent-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=prompt,
    )
    # Stream the response chunks
    output = []
    for event in response.get("completion", []):
        if "chunk" in event:
            output.append(event["chunk"]["bytes"].decode())
    return "".join(output)


# ---------------------------------------------------------------------------
# Demo / local test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--invoke", action="store_true", help="Test pattern 2 (boto3 invoke)")
    args = parser.parse_args()

    if args.invoke:
        result = invoke_bedrock_agent(
            agent_id=os.environ.get("BEDROCK_AGENT_ID", "XXXXXXXXXX"),
            agent_alias_id=os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID"),
            session_id="demo-session-001",
            prompt="Query the users table and send a report to admin@example.com",
        )
        print(f"Agent response:\n{result}")
    else:
        # Simulate a Lambda invocation
        mock_event = {
            "actionGroup": "DatabaseActions",
            "function": "query_database",
            "parameters": [{"name": "table", "value": "users"}],
            "invocationId": "mock-invocation-001",
        }
        result = bedrock_action_group_handler(mock_event, None)
        print(f"Lambda response:\n{json.dumps(result, indent=2)}")
