"""Anthropic Claude tool-use integration.

Same pattern as the OpenAI example, but using Claude's ``tool_use`` /
``tool_result`` content blocks. Every tool invocation is gated by Kynara;
``deny`` returns an ``error`` content block; ``require_approval`` returns
a content block carrying the approval URL so Claude can surface it to the
user.

Run:
    ANTHROPIC_API_KEY=... KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_demo \\
    python sdk/examples/anthropic_tool_use.py
"""
from __future__ import annotations

import json
import os

import anthropic                                                # type: ignore
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired

kynara = Kynara.from_env()
client = anthropic.Anthropic()


TOOLS = [
    {
        "name": "crm_contacts_read",
        "description": "Read a CRM contact record by id",
        "input_schema": {
            "type": "object",
            "properties": {"contact_id": {"type": "string"}},
            "required": ["contact_id"],
        },
    },
    {
        "name": "payments_refund_issue",
        "description": "Issue a refund for a charge",
        "input_schema": {
            "type": "object",
            "properties": {
                "refund_id": {"type": "string"},
                "amount_cents": {"type": "integer"},
            },
            "required": ["refund_id", "amount_cents"],
        },
    },
]


ACTION_FOR = {
    "crm_contacts_read":     "crm.contacts.read",
    "payments_refund_issue": "payments.refund.issue",
}
RESOURCE_FOR = {
    "crm_contacts_read": lambda a: {"type": "crm.contact", "id": a["contact_id"],
                                     "attrs": {"classification": "pii"}},
    "payments_refund_issue": lambda a: {"type": "payment.refund", "id": a["refund_id"],
                                         "attrs": {"amount_cents": a["amount_cents"]}},
}


def call_tool(name: str, input_: dict) -> dict:
    try:
        kynara.enforce(
            subject=("agent", os.environ["KYNARA_AGENT_ID"]),
            action=ACTION_FOR[name],
            resource=RESOURCE_FOR[name](input_),
            context={"framework": "anthropic-claude"},
        )
    except PermissionDenied as e:
        return {"error": "permission_denied", "reason": e.decision.reason}
    except ApprovalRequired as e:
        return {"error": "approval_required",
                "approval_url": e.decision.approval_url,
                "decision_id": e.decision.decision_id}

    if name == "crm_contacts_read":
        return {"id": input_["contact_id"], "name": "Demo"}
    if name == "payments_refund_issue":
        return {"refund_id": input_["refund_id"], "status": "issued"}
    return {"error": "unknown_tool"}


def run(prompt: str) -> None:
    messages = [{"role": "user", "content": prompt}]
    while True:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            print(next((b.text for b in resp.content if b.type == "text"), ""))
            return

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            result = call_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    run("Pull contact c_1842, then refund r_77 for $1240 if appropriate.")
