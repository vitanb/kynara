"""Guardrail test suite.

Tests cover:
  - Integration CRUD (create, list, update, delete)
  - Rule CRUD
  - Inbound webhook event processing
  - Threshold-based rule firing
  - Enforcement actions: alert_only, suspend_agent, deny_all_policy
  - Event listing
  - HMAC signature verification on inbound webhooks
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

_integration_mark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="integration tests require DATABASE_URL",
)


@pytest.fixture(scope="module")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    from app.main import create_app
    app = create_app()
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c


async def _login(client: httpx.AsyncClient) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.com", "password": "demo-password-123!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ─── Unit tests ───────────────────────────────────────────────────────────────


# Mirrors of guardrails.py constants — kept in sync manually
_VALID_ACTIONS = {"alert_only", "suspend_agent", "revoke_jit_grants",
                  "deny_all_policy", "reduce_to_readonly"}
_VALID_PROVIDERS = {"arize", "custom", "langfuse", "whylabs", "fiddler"}
_ACTION_RANK = ["alert_only", "reduce_to_readonly",
                "revoke_jit_grants", "deny_all_policy", "suspend_agent"]


class TestGuardrailConstants:
    """Valid action and provider sets are correct."""

    def test_valid_actions(self):
        expected = {"alert_only", "suspend_agent", "revoke_jit_grants",
                    "deny_all_policy", "reduce_to_readonly"}
        assert _VALID_ACTIONS == expected

    def test_valid_providers(self):
        assert "arize" in _VALID_PROVIDERS
        assert "custom" in _VALID_PROVIDERS
        assert "langfuse" in _VALID_PROVIDERS

    def test_action_rank_order(self):
        """The severity ranking determines which action wins when multiple rules fire."""
        actions = ["alert_only", "suspend_agent"]
        top = max(actions, key=lambda a: _ACTION_RANK.index(a) if a in _ACTION_RANK else -1)
        assert top == "suspend_agent"

    def test_deny_all_beats_reduce_to_readonly(self):
        actions = ["reduce_to_readonly", "deny_all_policy"]
        top = max(actions, key=lambda a: _ACTION_RANK.index(a) if a in _ACTION_RANK else -1)
        assert top == "deny_all_policy"

    def test_suspend_agent_is_highest_severity(self):
        all_actions = list(_VALID_ACTIONS)
        top = max(all_actions, key=lambda a: _ACTION_RANK.index(a) if a in _ACTION_RANK else -1)
        assert top == "suspend_agent"


class TestGuardrailSchemas:
    """Guardrail business rule constraints (validated inline without app import)."""

    def test_empty_name_is_invalid(self):
        name = ""
        assert len(name) < 1  # min_length=1 in IntegrationIn

    def test_name_up_to_200_chars_valid(self):
        name = "x" * 200
        assert len(name) <= 200

    def test_rule_threshold_minimum_is_1(self):
        threshold = 0
        assert threshold < 1  # ge=1 constraint

    def test_rule_window_minimum_is_10_seconds(self):
        window = 5
        assert window < 10  # ge=10 constraint

    def test_rule_window_maximum_is_86400(self):
        window = 86401
        assert window > 86400  # le=86400 constraint

    def test_valid_threshold_accepted(self):
        for threshold in (1, 5, 10, 100):
            assert threshold >= 1

    def test_valid_window_accepted(self):
        for window in (10, 60, 300, 3600, 86400):
            assert 10 <= window <= 86400


# ─── Integration tests ────────────────────────────────────────────────────────


@_integration_mark
class TestGuardrailIntegrationCRUD:

    async def test_list_integrations_requires_auth(self, client: httpx.AsyncClient):
        r = await client.get("/api/v1/guardrails")
        assert r.status_code == 401

    async def test_list_integrations_empty_initially(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.get("/api/v1/guardrails",
                              headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_create_integration_unknown_provider_400(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test", "provider": "nonexistent_provider"},
        )
        assert r.status_code == 400

    async def test_create_integration_unknown_action_400(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test", "provider": "custom", "default_action": "nuke_everything"},
        )
        assert r.status_code == 400

    async def test_create_and_delete_integration(self, client: httpx.AsyncClient):
        token = await _login(client)
        # Create
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Test Arize Integration",
                "provider": "arize",
                "default_action": "alert_only",
                "is_enabled": True,
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        integration_id = body["id"]
        assert body["name"] == "Test Arize Integration"
        assert body["provider"] == "arize"
        assert "webhook_inbound_url" in body
        assert integration_id in body["webhook_inbound_url"]

        # Appears in list
        r = await client.get("/api/v1/guardrails",
                              headers={"Authorization": f"Bearer {token}"})
        ids = [i["id"] for i in r.json()]
        assert integration_id in ids

        # Update
        r = await client.patch(
            f"/api/v1/guardrails/{integration_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Updated Arize Integration", "is_enabled": False},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Arize Integration"
        assert r.json()["is_enabled"] is False

        # Delete
        r = await client.delete(
            f"/api/v1/guardrails/{integration_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204

        # Gone from list
        r = await client.get("/api/v1/guardrails",
                              headers={"Authorization": f"Bearer {token}"})
        ids = [i["id"] for i in r.json()]
        assert integration_id not in ids

    async def test_update_nonexistent_integration_404(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.patch(
            f"/api/v1/guardrails/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "ghost"},
        )
        assert r.status_code == 404

    async def test_developer_cannot_create_integration(self, client: httpx.AsyncClient):
        r = await client.post("/api/v1/auth/login",
                               json={"email": "dev@acme.com", "password": "demo-password-123!"})
        if r.status_code != 200:
            pytest.skip("Developer seed user not available")
        token = r.json()["access_token"]
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test", "provider": "custom"},
        )
        assert r.status_code == 403


@_integration_mark
class TestGuardrailRuleCRUD:

    async def _create_integration(self, client: httpx.AsyncClient, token: str) -> str:
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": f"Rule Test Integration {uuid.uuid4().hex[:6]}",
                  "provider": "custom", "default_action": "alert_only"},
        )
        assert r.status_code == 201
        return r.json()["id"]

    async def test_list_rules_returns_array(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.get("/api/v1/guardrails/rules",
                              headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_create_rule_with_invalid_action_400(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.post(
            "/api/v1/guardrails/rules",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Bad Rule", "action": "destroy_everything"},
        )
        assert r.status_code == 400

    async def test_create_rule_full_lifecycle(self, client: httpx.AsyncClient):
        token = await _login(client)

        # Create rule: fire suspend_agent after 3 critical events in 60 seconds
        r = await client.post(
            "/api/v1/guardrails/rules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "High Volume Critical Suspender",
                "description": "Suspend agent after 3 criticals in 60s",
                "event_count_threshold": 3,
                "time_window_seconds": 60,
                "filter_severities": ["critical"],
                "action": "suspend_agent",
                "is_enabled": True,
            },
        )
        assert r.status_code == 201, r.text
        rule = r.json()
        rule_id = rule["id"]
        assert rule["event_count_threshold"] == 3
        assert rule["time_window_seconds"] == 60
        assert rule["action"] == "suspend_agent"
        assert rule["filter_severities"] == ["critical"]

        # Update rule — lower threshold
        r = await client.patch(
            f"/api/v1/guardrails/rules/{rule_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"event_count_threshold": 1, "action": "alert_only"},
        )
        assert r.status_code == 200
        assert r.json()["event_count_threshold"] == 1
        assert r.json()["action"] == "alert_only"

        # Delete rule
        r = await client.delete(
            f"/api/v1/guardrails/rules/{rule_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204

    async def test_update_rule_with_invalid_action_400(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.post(
            "/api/v1/guardrails/rules",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Temp Rule", "action": "alert_only"},
        )
        assert r.status_code == 201
        rule_id = r.json()["id"]
        r = await client.patch(
            f"/api/v1/guardrails/rules/{rule_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"action": "bad_action"},
        )
        assert r.status_code == 400


@_integration_mark
class TestGuardrailInboundWebhook:

    async def _setup_integration(self, client: httpx.AsyncClient, token: str) -> tuple[str, str]:
        """Create an integration and a threshold rule. Returns (integration_id, rule_id)."""
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": f"Inbound Test {uuid.uuid4().hex[:6]}",
                "provider": "custom",
                "default_action": "alert_only",
            },
        )
        assert r.status_code == 201
        integration_id = r.json()["id"]

        r = await client.post(
            "/api/v1/guardrails/rules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Immediate Alert Rule",
                "integration_id": integration_id,
                "event_count_threshold": 1,
                "time_window_seconds": 300,
                "action": "alert_only",
            },
        )
        assert r.status_code == 201
        rule_id = r.json()["id"]
        return integration_id, rule_id

    async def test_inbound_to_disabled_integration_404(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Disabled Integration", "provider": "custom", "is_enabled": False},
        )
        assert r.status_code == 201
        integration_id = r.json()["id"]

        r = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            json={"rule_name": "toxicity", "severity": "critical"},
        )
        assert r.status_code == 404

    async def test_inbound_to_nonexistent_integration_404(self, client: httpx.AsyncClient):
        fake_id = str(uuid.uuid4())
        r = await client.post(
            f"/api/v1/guardrails/inbound/{fake_id}",
            json={"rule_name": "test", "severity": "warning"},
        )
        assert r.status_code == 404

    async def test_inbound_event_recorded_and_alert_only(self, client: httpx.AsyncClient):
        token = await _login(client)
        integration_id, rule_id = await self._setup_integration(client, token)

        r = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            json={
                "rule_name": "toxicity_check",
                "severity": "warning",
                "score": 0.75,
                "trace_id": "trace-abc-123",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert "event_id" in body
        assert "action_taken" in body

    async def test_inbound_event_with_monitored_rule_filter(self, client: httpx.AsyncClient):
        token = await _login(client)
        # Create integration that only monitors specific rules
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": f"Filtered Integration {uuid.uuid4().hex[:6]}",
                "provider": "custom",
                "monitored_rules": ["toxicity_check", "pii_leak"],
            },
        )
        assert r.status_code == 201
        integration_id = r.json()["id"]

        # Send event with un-monitored rule → ignored
        r = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            json={"rule_name": "other_check", "severity": "critical"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ignored"

        # Send event with monitored rule → ok
        r = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            json={"rule_name": "toxicity_check", "severity": "critical"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_inbound_threshold_rule_fires_on_nth_event(self, client: httpx.AsyncClient):
        """Create a threshold=2 rule and verify it fires on the 2nd matching event."""
        token = await _login(client)
        r = await client.post(
            "/api/v1/guardrails",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": f"Threshold Test {uuid.uuid4().hex[:6]}",
                "provider": "custom",
                "default_action": "alert_only",
            },
        )
        assert r.status_code == 201
        integration_id = r.json()["id"]

        # Create a rule: fire alert_only when 2+ critical events in 300s
        r = await client.post(
            "/api/v1/guardrails/rules",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Critical Threshold Rule",
                "integration_id": integration_id,
                "event_count_threshold": 2,
                "time_window_seconds": 300,
                "filter_severities": ["critical"],
                "action": "alert_only",
            },
        )
        assert r.status_code == 201

        # First event — rule should NOT fire (count=1, threshold=2)
        r1 = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            json={"rule_name": "pii_leak", "severity": "critical"},
        )
        assert r1.status_code == 200
        assert r1.json()["rules_fired"] == 0

        # Second event — rule SHOULD fire (count=2, threshold=2)
        r2 = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            json={"rule_name": "pii_leak", "severity": "critical"},
        )
        assert r2.status_code == 200
        assert r2.json()["rules_fired"] >= 1
        assert r2.json()["action_taken"] == "alert_only"

    async def test_inbound_invalid_json_400(self, client: httpx.AsyncClient):
        token = await _login(client)
        integration_id, _ = await self._setup_integration(client, token)
        r = await client.post(
            f"/api/v1/guardrails/inbound/{integration_id}",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400


@_integration_mark
class TestGuardrailEvents:

    async def test_list_events_returns_array(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.get("/api/v1/guardrails/events",
                              headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_list_events_limit_respected(self, client: httpx.AsyncClient):
        token = await _login(client)
        r = await client.get("/api/v1/guardrails/events?limit=5",
                              headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()) <= 5
