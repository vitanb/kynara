"""Decorator tests using an in-memory fake client (no HTTP)."""
from __future__ import annotations

import pytest

from kynara_sdk import permission_required, PermissionDenied
from kynara_sdk.context import set_current_kynara
from kynara_sdk.types import Decision, DecisionEffect


class FakeKynara:
    def __init__(self, effect: DecisionEffect):
        self.effect = effect
        self.calls = []

    def enforce(self, *, action, resource, context):
        self.calls.append((action, resource, context))
        if self.effect == DecisionEffect.DENY:
            raise PermissionDenied(
                Decision(effect=self.effect, reason="mocked", matched_policy_id="p"),
                action, "agent-x",
            )
        return Decision(effect=self.effect, reason="ok")


def test_decorator_allows():
    s = FakeKynara(DecisionEffect.ALLOW)
    set_current_kynara(s)

    @permission_required("crm.contacts.read", resource_arg="contact_id",
                        resource_type="crm.contact")
    def read_contact(contact_id):
        return {"id": contact_id}

    assert read_contact("c_1") == {"id": "c_1"}
    assert s.calls[0][0] == "crm.contacts.read"
    assert s.calls[0][1].id == "c_1"


def test_decorator_denies():
    s = FakeKynara(DecisionEffect.DENY)
    set_current_kynara(s)

    @permission_required("payments.refund.issue", resource_arg="payment_id")
    def refund(payment_id):
        return "should not run"

    with pytest.raises(PermissionDenied):
        refund("p_1")
