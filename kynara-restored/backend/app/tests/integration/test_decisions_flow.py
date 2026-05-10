"""End-to-end integration tests for the decision-check API.

Spins up the FastAPI app against a real Postgres + Redis (configured by the
CI workflow). Exercises the canonical paths a customer SDK would take.
"""
from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="integration tests require DATABASE_URL + REDIS_URL",
)


@pytest.fixture(scope="module")
async def client():
    from app.main import create_app
    app = create_app()
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c


async def test_login_and_check_allow(client: httpx.AsyncClient):
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@acme.com", "password": "demo-password-123!",
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = await client.post(
        "/api/v1/decisions/check",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subject_type": "agent",
            "subject_id": "crm-assistant",
            "action": "crm.contacts.read",
            "resource": {"type": "crm.contact", "id": "c_1", "attrs": {"classification": "public"}},
            "context": {"ip_country": "US"},
        },
    )
    assert r.status_code == 200, r.text
    decision = r.json()
    assert decision["effect"] in ("allow", "require_approval")


async def test_audit_chain_verify(client: httpx.AsyncClient):
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@acme.com", "password": "demo-password-123!",
    })
    token = r.json()["access_token"]

    r = await client.post(
        "/api/v1/audit/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True, r.json()


async def test_tenant_isolation_via_rls(client: httpx.AsyncClient):
    """Cannot read another org's policies even with a valid token."""
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@acme.com", "password": "demo-password-123!",
    })
    token = r.json()["access_token"]

    # Try to fetch a policy by a UUID from a different tenant.
    other_tenant_uuid = "00000000-0000-0000-0000-000000000999"
    r = await client.get(
        f"/api/v1/policies/{other_tenant_uuid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (404, 403)


async def test_fail_closed_on_deny(client: httpx.AsyncClient):
    """A request that matches a deny policy returns deny, never allow."""
    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@acme.com", "password": "demo-password-123!",
    })
    token = r.json()["access_token"]

    r = await client.post(
        "/api/v1/decisions/check",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subject_type": "agent",
            "subject_id": "support-triage",   # autonomous in seed
            "action": "payments.refund.issue",
            "resource": {"type": "payment.refund", "attrs": {"amount_cents": 5000}},
            "context": {"ip_country": "US"},
        },
    )
    assert r.status_code == 200
    assert r.json()["effect"] == "deny"
