"""Unit tests for the pure policy engine (no DB required)."""
from __future__ import annotations

import pytest

from app.policy.engine import (
    Decision,
    DecisionContext,
    EngineInput,
    _PolicyRow,
    evaluate,
)


def _ctx(action="crm.contacts.read", resource_type="crm.contact", attrs=None, context=None):
    return DecisionContext(
        subject={"id": "a", "type": "agent", "attrs": attrs or {"scopes": ["*"]}},
        action=action,
        resource={"type": resource_type, "id": "r1", "attrs": {}},
        context=context or {},
    )


def test_rbac_default_deny():
    d = evaluate(EngineInput(policies=[], granted_scopes=[]),
                 _ctx(attrs={"scopes": []}))
    assert d.effect == "deny"
    assert "no role grants" in d.reason


def test_rbac_wildcard():
    d = evaluate(EngineInput(policies=[], granted_scopes=["*"]),
                 _ctx())
    # no policies + no default → default deny
    assert d.effect == "deny"


def test_allow_policy_matches():
    p = _PolicyRow(id="p1", priority=100, effect="allow",
                   actions=["crm.*"], resource_types=["crm.contact"],
                   condition={})
    d = evaluate(EngineInput(policies=[p], granted_scopes=["crm.contacts.read"]), _ctx())
    assert d.effect == "allow"
    assert d.matched_policy_id == "p1"


def test_deny_overrides_by_priority():
    allow = _PolicyRow(id="a", priority=200, effect="allow",
                       actions=["crm.*"], resource_types=[], condition={})
    deny = _PolicyRow(id="d", priority=100, effect="deny",
                      actions=["crm.*"], resource_types=[], condition={})
    d = evaluate(EngineInput(policies=[allow, deny],
                             granted_scopes=["crm.contacts.read"]), _ctx())
    assert d.effect == "deny"
    assert d.matched_policy_id == "d"


def test_time_window_condition():
    p = _PolicyRow(id="p", priority=100, effect="allow",
                   actions=["crm.*"], resource_types=[],
                   condition={"op": "time_between",
                              "args": ["ctx.context.time", "09:00", "18:00"]})
    inside = _ctx(context={"time": "2026-04-01T10:30:00+00:00"})
    outside = _ctx(context={"time": "2026-04-01T02:00:00+00:00"})

    assert evaluate(EngineInput([p], ["*"]), inside).effect == "allow"
    assert evaluate(EngineInput([p], ["*"]), outside).effect == "deny"


def test_require_approval_effect():
    p = _PolicyRow(id="p", priority=100, effect="require_approval",
                   actions=["payments.*"], resource_types=[],
                   condition={"op": "gt", "args": ["ctx.resource.attrs.amount_cents", 10000]})
    ctx = DecisionContext(
        subject={"id": "a", "type": "agent", "attrs": {"scopes": ["payments.refund.issue"]}},
        action="payments.refund.issue",
        resource={"type": "payment", "id": "p1", "attrs": {"amount_cents": 50000}},
        context={},
    )
    d = evaluate(EngineInput([p], ["payments.refund.issue"]), ctx)
    assert d.effect == "require_approval"
