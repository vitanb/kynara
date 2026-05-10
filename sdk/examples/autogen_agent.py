"""Microsoft AutoGen integration.

AutoGen's ``register_for_llm``/``register_for_execution`` decorators are the
hook point. We add a small wrapper that calls Kynara before the underlying
function runs. ``deny`` raises so the agent loop reflects the failure;
``require_approval`` returns a structured payload AutoGen can surface.

Run:
    OPENAI_API_KEY=... KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_demo \\
    python sdk/examples/autogen_agent.py
"""
from __future__ import annotations

import functools
import os

import autogen                                                         # type: ignore
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired

kynara = Kynara.from_env()


def kynara_tool(*, action: str, resource_factory):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                kynara.enforce(
                    subject=("agent", os.environ["KYNARA_AGENT_ID"]),
                    action=action,
                    resource=resource_factory(*args, **kwargs),
                    context={"framework": "autogen"},
                )
            except PermissionDenied as e:
                return {"error": "permission_denied", "reason": e.decision.reason}
            except ApprovalRequired as e:
                return {"error": "approval_required",
                        "approval_url": e.decision.approval_url}
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ─── Tools ──────────────────────────────────────────────────────────────────

@kynara_tool(
    action="crm.contacts.read",
    resource_factory=lambda contact_id: {
        "type": "crm.contact", "id": contact_id, "attrs": {"classification": "pii"},
    },
)
def crm_read(contact_id: str) -> dict:
    return {"id": contact_id, "name": "Demo"}


@kynara_tool(
    action="payments.refund.issue",
    resource_factory=lambda refund_id, amount_cents: {
        "type": "payment.refund", "id": refund_id,
        "attrs": {"amount_cents": amount_cents},
    },
)
def refund(refund_id: str, amount_cents: int) -> dict:
    return {"refund_id": refund_id, "status": "issued"}


# ─── Wire up an AutoGen GroupChat ───────────────────────────────────────────

ops = autogen.AssistantAgent(
    name="ops_agent",
    system_message=(
        "You are a customer operations agent. Use tools when appropriate. "
        "If a tool returns 'approval_required' or 'permission_denied', "
        "explain the situation and stop."
    ),
    llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ["OPENAI_API_KEY"]}]},
)
user = autogen.UserProxyAgent(
    name="user",
    code_execution_config=False,
    function_map={"crm_read": crm_read, "refund": refund},
)


if __name__ == "__main__":
    user.initiate_chat(
        ops,
        message="Look up c_1842 and refund r_77 for $1240 if rules allow.",
    )
