"""Kynara runtime enforcement SDK.

Three ways to enforce permissions around an agent's tool call:

1. **Decorator** — the ergonomic default.

    >>> from kynara_sdk import Kynara, permission_required
    >>> kynara = Kynara(api_key="sk_live_...", agent_id="...", user_id="...")
    >>>
    >>> @permission_required("crm.contacts.read", resource_arg="contact_id",
    ...                     resource_type="crm.contact")
    ... def read_contact(contact_id: str):
    ...     return {"id": contact_id, ...}

2. **Context manager** — when you need to check *before* a side-effect but act *after*.

    >>> with kynara.guard("payments.refund.issue",
    ...                    resource={"type":"payment","id":payment_id,
    ...                              "attrs":{"amount_cents": 50000}}) as grant:
    ...     grant.check()
    ...     issue_refund(payment_id)
    ...     grant.confirm(outcome="success")

3. **Middleware** — wrap a whole framework's tool dispatch.

    >>> from kynara_sdk.langchain import KynaraCallbackHandler
    >>> llm.callbacks = [KynaraCallbackHandler(kynara)]

In all three cases, denied calls raise ``PermissionDenied`` *before* the wrapped function
runs, and every evaluation is recorded in the Kynara audit log.
"""
from kynara_sdk.client import Kynara
from kynara_sdk.decorator import permission_required
from kynara_sdk.errors import (
    ApprovalRequired,
    PermissionDenied,
    KynaraError,
    KynaraUnavailable,
)
from kynara_sdk.types import Decision, DecisionEffect, Resource

__all__ = [
    "Kynara",
    "permission_required",
    "PermissionDenied",
    "ApprovalRequired",
    "KynaraError",
    "KynaraUnavailable",
    "Decision",
    "DecisionEffect",
    "Resource",
]
__version__ = "0.1.0"
