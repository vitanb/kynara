"""OpenAI Assistants / tool-use integration.

OpenAI's tool-call protocol is identical regardless of which model serves
the request — the Assistants API, the Chat Completions API, and the
Responses API all hand the runtime a list of tool calls each turn. This
example wraps a generic tool dispatcher so Kynara is consulted *before*
each call and ``deny`` short-circuits the loop.

Run:
    OPENAI_API_KEY=...  KYNARA_API_KEY=...  KYNARA_AGENT_ID=agent_demo \\
    python sdk/examples/openai_assistants.py
"""
from __future__ import annotations

import json
import os

from openai import OpenAI                                    # type: ignore
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired

kynara = Kynara.from_env()
client = OpenAI()


# ─── Tool definitions exposed to the model ──────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "crm_contacts_read",
            "description": "Read a CRM contact record by id",
            "parameters": {
                "type": "object",
                "properties": {"contact_id": {"type": "string"}},
                "required": ["contact_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "payments_refund_issue",
            "description": "Issue a refund for a charge",
            "parameters": {
                "type": "object",
                "properties": {
                    "refund_id": {"type": "string"},
                    "amount_cents": {"type": "integer"},
                },
                "required": ["refund_id", "amount_cents"],
            },
        },
    },
]


# ─── Tool implementations (placeholders) ────────────────────────────────────

def crm_contacts_read(contact_id: str) -> dict:
    return {"id": contact_id, "name": "Demo Contact", "email": "demo@example.com"}


def payments_refund_issue(refund_id: str, amount_cents: int) -> dict:
    return {"refund_id": refund_id, "amount_cents": amount_cents, "status": "issued"}


TOOL_IMPL = {
    "crm_contacts_read":     crm_contacts_read,
    "payments_refund_issue": payments_refund_issue,
}


# ─── Kynara-guarded dispatcher ─────────────────────────────────────────────

ACTION_FOR = {
    "crm_contacts_read":     "crm.contacts.read",
    "payments_refund_issue": "payments.refund.issue",
}

RESOURCE_FOR = {
    "crm_contacts_read": lambda args: {
        "type": "crm.contact",
        "id": args["contact_id"],
        "attrs": {"classification": "pii"},
    },
    "payments_refund_issue": lambda args: {
        "type": "payment.refund",
        "id": args["refund_id"],
        "attrs": {"amount_cents": args["amount_cents"], "currency": "USD"},
    },
}


def dispatch_tool_call(name: str, args: dict) -> str:
    """Enforce Kynara, then run, returning a string the model can read."""
    try:
        kynara.enforce(
            subject=("agent", os.environ["KYNARA_AGENT_ID"]),
            action=ACTION_FOR[name],
            resource=RESOURCE_FOR[name](args),
            context={"framework": "openai-assistants"},
        )
    except PermissionDenied as e:
        return json.dumps({"error": "permission_denied", "reason": e.decision.reason})
    except ApprovalRequired as e:
        return json.dumps({
            "error": "approval_required",
            "approval_url": e.decision.approval_url,
            "decision_id": e.decision.decision_id,
        })

    fn = TOOL_IMPL[name]
    return json.dumps(fn(**args))


def run(user_message: str) -> None:
    messages = [{"role": "user", "content": user_message}]
    while True:
        resp = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, tools=TOOLS,
        )
        choice = resp.choices[0]
        msg = choice.message
        messages.append(msg)

        if not msg.tool_calls:
            print(msg.content)
            return

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = dispatch_tool_call(name, args)
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": result,
            })


if __name__ == "__main__":
    run("Look up contact c_1842 and refund payment r_77 for $1240")
