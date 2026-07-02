"""Unit tests for the `is_tainted` operator and dynamic-downgrade evaluation.

Run from the backend/ directory:
    pytest tests/test_taint_engine.py -q
"""
from app.policy.engine import (
    DecisionContext,
    EngineInput,
    _PolicyRow,
    _taint_state,
    evaluate,
)


def _ctx(context):
    return DecisionContext(
        subject={"id": "a1", "type": "agent", "attrs": {"scopes": ["email.send"]}},
        action="email.send",
        resource={"type": "mcp_tool", "id": "email.send", "attrs": {}},
        context=context,
    )


class TestTaintState:
    def test_clean_context(self):
        assert _taint_state(_ctx({})) == (set(), False)

    def test_bool_true_is_generic(self):
        assert _taint_state(_ctx({"taint": True})) == (set(), True)

    def test_string_marker(self):
        markers, generic = _taint_state(_ctx({"taint": "untrusted_web"}))
        assert markers == {"untrusted_web"} and generic is False

    def test_list_markers(self):
        markers, generic = _taint_state(_ctx({"taint": ["untrusted_web", "external_email"]}))
        assert markers == {"untrusted_web", "external_email"} and generic is False

    def test_trust_level_untrusted_is_generic(self):
        assert _taint_state(_ctx({"trust_level": "untrusted"}))[1] is True

    def test_trust_level_high_is_clean(self):
        assert _taint_state(_ctx({"trust_level": "high"})) == (set(), False)


def _engine(effect, condition):
    return EngineInput(
        policies=[_PolicyRow(
            id="p-egress", priority=10, effect=effect,
            actions=["email.send"], resource_types=[], condition=condition,
        )],
        granted_scopes=["email.send"],
        default_effect="allow",
    )


class TestIsTaintedEvaluation:
    def test_generic_is_tainted_denies_when_tainted(self):
        dec = evaluate(_engine("deny", {"op": "is_tainted"}), _ctx({"taint": True}))
        assert dec.effect == "deny" and dec.matched_policy_id == "p-egress"

    def test_generic_is_tainted_allows_when_clean(self):
        # policy condition false -> no match -> default allow
        dec = evaluate(_engine("deny", {"op": "is_tainted"}), _ctx({}))
        assert dec.effect == "allow"

    def test_named_marker_matches(self):
        dec = evaluate(
            _engine("require_approval", {"op": "is_tainted", "args": ["untrusted_web"]}),
            _ctx({"taint": ["untrusted_web"]}),
        )
        assert dec.effect == "require_approval"

    def test_named_marker_no_match_other_category(self):
        dec = evaluate(
            _engine("deny", {"op": "is_tainted", "args": ["untrusted_web"]}),
            _ctx({"taint": ["external_email"]}),
        )
        assert dec.effect == "allow"  # condition false -> default

    def test_generic_taint_matches_named_query_failsafe(self):
        # taint == True must satisfy a category-scoped policy (over-restrict).
        dec = evaluate(
            _engine("deny", {"op": "is_tainted", "args": ["untrusted_web"]}),
            _ctx({"taint": True}),
        )
        assert dec.effect == "deny"
