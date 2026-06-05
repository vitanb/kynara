"""Unit tests for Okta identity normalization + role mapping.

Run from backend/:
    pytest tests/test_okta_idp.py -q
"""
from app.idp.okta import normalize_identity, role_for_groups


class TestNormalizeIdentity:
    def test_agent_object(self):
        n = normalize_identity({"id": "a1", "name": "CRM Bot", "status": "ACTIVE"})
        assert n["external_id"] == "a1"
        assert n["display_name"] == "CRM Bot"
        assert n["status"] == "ACTIVE"
        assert n["groups"] == []

    def test_user_object_first_last(self):
        n = normalize_identity({
            "id": "u1", "status": "ACTIVE",
            "profile": {"login": "bot@acme.com", "firstName": "CRM", "lastName": "Bot"},
        })
        assert n["external_id"] == "u1"
        assert n["display_name"] == "CRM Bot"
        assert n["login"] == "bot@acme.com"

    def test_display_name_preference(self):
        n = normalize_identity({"id": "u2", "profile": {"displayName": "Refund Agent", "login": "r@a.com"}})
        assert n["display_name"] == "Refund Agent"

    def test_missing_id(self):
        assert normalize_identity({"profile": {}})["external_id"] == ""

    def test_falls_back_to_id_when_no_name(self):
        n = normalize_identity({"id": "x9"})
        assert n["display_name"] == "x9"


class TestRoleForGroups:
    def test_first_match_wins(self):
        mapping = {"AI Agents - CRM": "crm-reader", "AI Agents - Billing": "billing"}
        assert role_for_groups(["Everyone", "AI Agents - CRM"], mapping) == "crm-reader"

    def test_no_match_returns_none(self):
        assert role_for_groups(["Everyone"], {"AI Agents - CRM": "crm-reader"}) is None

    def test_empty_mapping(self):
        assert role_for_groups(["Everyone"], {}) is None
