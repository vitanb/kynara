# kynara-sdk

Runtime enforcement for AI agents built on the Kynara control plane.

## Install

```bash
pip install kynara-sdk
```

## Decorator

```python
from kynara_sdk import Kynara, permission_required
from kynara_sdk.context import set_current_kynara

set_current_kynara(Kynara(
    api_key=os.environ["KYNARA_API_KEY"],
    agent_id="crm-assistant",
    user_id=current_user_id,
    fail_closed=True,
))

@permission_required("crm.contacts.read", resource_arg="contact_id",
                    resource_type="crm.contact")
def read_contact(contact_id: str):
    return crm.get(contact_id)
```

If policy denies the call, `PermissionDenied` is raised *before* `crm.get` runs and the
attempt is recorded in the audit log. If policy returns `require_approval`,
`ApprovalRequired` is raised — your agent should pause, emit an approval request, and
re-invoke once `context["approval_token"]` is populated.

## Context manager

```python
with kynara.guard(
    "payments.refund.issue",
    resource={"type":"payment","id":payment_id,
              "attrs":{"amount_cents": 50000}},
) as grant:
    result = issue_refund(payment_id)
    # grant auto-confirms success on clean exit; error outcome auto-recorded on raise
```

## LangChain

```python
from kynara_sdk.langchain import KynaraCallbackHandler
agent_executor.callbacks = [KynaraCallbackHandler(kynara)]
```

## Failure modes

| Setting              | Behavior                                                          |
|----------------------|-------------------------------------------------------------------|
| `fail_closed=True`   | Control-plane unreachable → `KynaraUnavailable` raised (default)|
| `fail_closed=False`  | Control-plane unreachable → treat as `allow` and log locally      |

Default is fail-closed. Only flip to fail-open in non-production or for explicit
read-only tools where unavailability of the control plane is less risky than blocking.

## Caching

Decisions are cached in-process for 5 seconds (configurable) keyed by
`(agent_id, user_id, action, resource_id)`. `require_approval` decisions are **never**
cached — they must re-check every time.
