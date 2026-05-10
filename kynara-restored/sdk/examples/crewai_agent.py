"""CrewAI integration: gate every Tool through Kynara.

CrewAI tools are subclasses of ``BaseTool``. Wrap each one with
``@kynara_guard`` to enforce a Kynara check before ``_run`` executes.

Run:
    KYNARA_API_KEY=... KYNARA_AGENT_ID=agent_demo \\
    python sdk/examples/crewai_agent.py
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable

from crewai import Agent, Task, Crew                                # type: ignore
from crewai.tools import BaseTool                                    # type: ignore
from kynara_sdk import Kynara, PermissionDenied, ApprovalRequired

kynara = Kynara.from_env()


def kynara_guard(action: str, resource_factory: Callable[..., dict]):
    """Decorator factory for CrewAI ``BaseTool._run``."""
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapped(self, *args, **kwargs):
            try:
                kynara.enforce(
                    subject=("agent", os.environ["KYNARA_AGENT_ID"]),
                    action=action,
                    resource=resource_factory(*args, **kwargs),
                    context={"framework": "crewai", "tool": self.name},
                )
            except PermissionDenied as e:
                return f"DENIED ({e.decision.reason})"
            except ApprovalRequired as e:
                return f"NEEDS APPROVAL: {e.decision.approval_url}"
            return fn(self, *args, **kwargs)
        return wrapped
    return deco


class CrmReadTool(BaseTool):
    name: str = "crm_contacts_read"
    description: str = "Read a CRM contact"

    @kynara_guard(
        action="crm.contacts.read",
        resource_factory=lambda contact_id: {
            "type": "crm.contact", "id": contact_id, "attrs": {"classification": "pii"},
        },
    )
    def _run(self, contact_id: str) -> str:
        return f"Contact {contact_id}: Demo Contact <demo@example.com>"


class RefundTool(BaseTool):
    name: str = "payments_refund_issue"
    description: str = "Issue a refund"

    @kynara_guard(
        action="payments.refund.issue",
        resource_factory=lambda refund_id, amount_cents: {
            "type": "payment.refund", "id": refund_id,
            "attrs": {"amount_cents": amount_cents, "currency": "USD"},
        },
    )
    def _run(self, refund_id: str, amount_cents: int) -> str:
        return f"refund {refund_id} for ${amount_cents/100:.2f}: issued"


if __name__ == "__main__":
    agent = Agent(
        role="Customer Operations",
        goal="Resolve refund requests safely",
        backstory="A diligent ops agent that respects company policies.",
        tools=[CrmReadTool(), RefundTool()],
    )
    crew = Crew(agents=[agent], tasks=[
        Task(description="Look up c_1842 then refund r_77 ($1240)", agent=agent),
    ])
    crew.kickoff()
