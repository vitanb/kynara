"""
Guardrail integration endpoints.

Provides:
  CRUD  - manage guardrail integrations per org
  Rules - threshold-based auto-revocation rules
  POST  /guardrails/inbound/{integration_id}
          Receive a webhook event from Arize / Langfuse / WhyLabs / custom.
          Records the event, then evaluates all enabled GuardrailRules.
          A rule fires when matching event count in its time window >= threshold.

Actions:
  alert_only        -> audit log + org webhook, no enforcement
  suspend_agent     -> agent.is_active = False
  revoke_jit_grants -> expire all active JIT grants for the agent
  deny_all_policy   -> insert temporary deny-all policy
  reduce_to_readonly-> deny non-read actions via policy
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator as pydantic_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_admin
from app.auth.dependencies import Principal, get_principal
from app.auth.passwords import hash_token
from app.core.ssrf import assert_safe_url
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.guardrail import GuardrailEvent, GuardrailIntegration, GuardrailRule
from app.models.jit_grant import JitGrant
from app.models.policy import Policy
from app.webhooks.service import emit

router = APIRouter(prefix="/guardrails", tags=["guardrails"])

VALID_ACTIONS = {
    "alert_only", "disable_agent", "suspend_agent", "revoke_jit_grants",
    "deny_all_policy", "reduce_to_readonly",
}
VALID_PROVIDERS = {
    "arize", "custom", "langfuse", "whylabs", "fiddler",
    "grafana", "datadog", "pagerduty", "newrelic", "prometheus",
}


async def _db():
    async with SessionLocal() as s:
        yield s


def _require_admin(p: Principal) -> None:
    if p.seat_role not in ("owner", "admin"):
        raise HTTPException(403, "Requires owner or admin role")


# ── Pydantic schemas — integrations ──────────────────────────────────────────

class IntegrationIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    provider: str
    webhook_secret: str | None = None
    api_key: str | None = None
    api_endpoint: str | None = None
    default_action: str = "alert_only"
    severity_action_map: dict[str, str] = {}
    agent_ids: list[str] | None = None
    monitored_rules: list[str] | None = None
    is_enabled: bool = True

    @pydantic_validator("api_endpoint")
    @classmethod
    def _validate_api_endpoint(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            assert_safe_url(v)
        except ValueError as exc:
            raise ValueError(f"api_endpoint is not allowed: {exc}") from exc
        return v


class IntegrationOut(BaseModel):
    id: str
    name: str
    provider: str
    default_action: str
    severity_action_map: dict
    agent_ids: list[str] | None
    monitored_rules: list[str] | None
    is_enabled: bool
    created_at: str
    webhook_inbound_url: str

    @classmethod
    def from_orm(cls, g: GuardrailIntegration, base_url: str) -> "IntegrationOut":
        return cls(
            id=str(g.id),
            name=g.name,
            provider=g.provider,
            default_action=g.default_action,
            severity_action_map=g.severity_action_map or {},
            agent_ids=[str(a) for a in g.agent_ids] if g.agent_ids else None,
            monitored_rules=g.monitored_rules,
            is_enabled=g.is_enabled,
            created_at=g.created_at.isoformat(),
            webhook_inbound_url=f"{base_url}/api/v1/guardrails/inbound/{g.id}",
        )


class GuardrailEventOut(BaseModel):
    id: str
    integration_id: str | None
    agent_id: str | None
    rule_name: str
    severity: str
    action_taken: str
    action_detail: dict
    payload: dict
    created_at: str

    @classmethod
    def from_orm(cls, e: GuardrailEvent) -> "GuardrailEventOut":
        return cls(
            id=str(e.id),
            integration_id=str(e.integration_id) if e.integration_id else None,
            agent_id=str(e.agent_id) if e.agent_id else None,
            rule_name=e.rule_name,
            severity=e.severity,
            action_taken=e.action_taken,
            action_detail=e.action_detail or {},
            payload=e.payload or {},
            created_at=e.created_at.isoformat(),
        )


# ── Pydantic schemas — rules ──────────────────────────────────────────────────

class RuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    integration_id: str | None = None   # null = applies to all integrations
    event_count_threshold: int = Field(default=1, ge=1)
    time_window_seconds: int = Field(default=300, ge=10, le=86400)
    filter_agent_ids: list[str] | None = None
    filter_severities: list[str] | None = None
    filter_rule_names: list[str] | None = None
    action: str = "alert_only"
    is_enabled: bool = True


class RuleOut(BaseModel):
    id: str
    name: str
    description: str | None
    integration_id: str | None
    event_count_threshold: int
    time_window_seconds: int
    filter_agent_ids: list[str] | None
    filter_severities: list[str] | None
    filter_rule_names: list[str] | None
    action: str
    is_enabled: bool
    created_at: str

    @classmethod
    def from_orm(cls, r: GuardrailRule) -> "RuleOut":
        return cls(
            id=str(r.id),
            name=r.name,
            description=r.description,
            integration_id=str(r.integration_id) if r.integration_id else None,
            event_count_threshold=r.event_count_threshold,
            time_window_seconds=r.time_window_seconds,
            filter_agent_ids=[str(a) for a in r.filter_agent_ids] if r.filter_agent_ids else None,
            filter_severities=r.filter_severities,
            filter_rule_names=r.filter_rule_names,
            action=r.action,
            is_enabled=r.is_enabled,
            created_at=r.created_at.isoformat(),
        )


# ── Integration CRUD ──────────────────────────────────────────────────────────

@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    rows = (await session.scalars(
        select(GuardrailIntegration)
        .where(GuardrailIntegration.organization_id == uuid.UUID(principal.org_id))
        .order_by(GuardrailIntegration.created_at)
    )).all()
    base = str(request.base_url).rstrip("/")
    return [IntegrationOut.from_orm(r, base) for r in rows]


@router.post("", response_model=IntegrationOut, status_code=201)
async def create_integration(
    request: Request,
    body: IntegrationIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    _require_admin(principal)
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(400, f"Unknown provider. Use: {VALID_PROVIDERS}")
    if body.default_action not in VALID_ACTIONS:
        raise HTTPException(400, f"Unknown action. Use: {VALID_ACTIONS}")

    g = GuardrailIntegration(
        organization_id=uuid.UUID(principal.org_id),
        name=body.name,
        provider=body.provider,
        webhook_secret_hash=hash_token(body.webhook_secret) if body.webhook_secret else None,
        api_key_hash=hash_token(body.api_key) if body.api_key else None,
        api_endpoint=body.api_endpoint,
        default_action=body.default_action,
        severity_action_map=body.severity_action_map,
        agent_ids=[uuid.UUID(a) for a in body.agent_ids] if body.agent_ids else None,
        monitored_rules=body.monitored_rules,
        is_enabled=body.is_enabled,
    )
    session.add(g)
    await session.flush()
    await record_admin(session, org_id=principal.org_id,
                       actor=f"user:{principal.email}",
                       event_type="guardrail.integration.created",
                       resource_type="guardrail_integration", resource_id=str(g.id),
                       payload={"name": g.name, "provider": g.provider})
    await session.commit()
    base = str(request.base_url).rstrip("/")
    return IntegrationOut.from_orm(g, base)


@router.patch("/{integration_id}", response_model=IntegrationOut)
async def update_integration(
    integration_id: str,
    request: Request,
    body: dict = Body(...),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    _require_admin(principal)
    g = await session.get(GuardrailIntegration, uuid.UUID(integration_id))
    if not g or str(g.organization_id) != principal.org_id:
        raise HTTPException(404, "Integration not found")
    allowed = {"name", "default_action", "severity_action_map",
               "agent_ids", "monitored_rules", "is_enabled", "api_endpoint"}
    for k, v in body.items():
        if k in allowed:
            if k == "agent_ids" and v is not None:
                v = [uuid.UUID(a) for a in v]
            setattr(g, k, v)
    await record_admin(session, org_id=principal.org_id,
                       actor=f"user:{principal.email}",
                       event_type="guardrail.integration.updated",
                       resource_type="guardrail_integration", resource_id=integration_id,
                       payload=body)
    await session.commit()
    base = str(request.base_url).rstrip("/")
    return IntegrationOut.from_orm(g, base)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    _require_admin(principal)
    g = await session.get(GuardrailIntegration, uuid.UUID(integration_id))
    if not g or str(g.organization_id) != principal.org_id:
        raise HTTPException(404, "Integration not found")
    await session.delete(g)
    await session.commit()


# ── Rule CRUD ─────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[RuleOut])
async def list_rules(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    rows = (await session.scalars(
        select(GuardrailRule)
        .where(GuardrailRule.organization_id == uuid.UUID(principal.org_id))
        .order_by(GuardrailRule.created_at)
    )).all()
    return [RuleOut.from_orm(r) for r in rows]


@router.post("/rules", response_model=RuleOut, status_code=201)
async def create_rule(
    body: RuleIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    _require_admin(principal)
    if body.action not in VALID_ACTIONS:
        raise HTTPException(400, f"Unknown action. Use: {VALID_ACTIONS}")

    r = GuardrailRule(
        organization_id=uuid.UUID(principal.org_id),
        integration_id=uuid.UUID(body.integration_id) if body.integration_id else None,
        name=body.name,
        description=body.description,
        event_count_threshold=body.event_count_threshold,
        time_window_seconds=body.time_window_seconds,
        filter_agent_ids=[uuid.UUID(a) for a in body.filter_agent_ids] if body.filter_agent_ids else None,
        filter_severities=body.filter_severities,
        filter_rule_names=body.filter_rule_names,
        action=body.action,
        is_enabled=body.is_enabled,
    )
    session.add(r)
    await session.flush()
    await record_admin(session, org_id=principal.org_id,
                       actor=f"user:{principal.email}",
                       event_type="guardrail.rule.created",
                       resource_type="guardrail_rule", resource_id=str(r.id),
                       payload={"name": r.name, "threshold": r.event_count_threshold,
                                "window_seconds": r.time_window_seconds, "action": r.action})
    await session.commit()
    return RuleOut.from_orm(r)


@router.patch("/rules/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: str,
    body: dict = Body(...),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    _require_admin(principal)
    r = await session.get(GuardrailRule, uuid.UUID(rule_id))
    if not r or str(r.organization_id) != principal.org_id:
        raise HTTPException(404, "Rule not found")
    allowed = {"name", "description", "event_count_threshold", "time_window_seconds",
               "filter_agent_ids", "filter_severities", "filter_rule_names",
               "action", "is_enabled"}
    for k, v in body.items():
        if k in allowed:
            if k == "filter_agent_ids" and v is not None:
                v = [uuid.UUID(a) for a in v]
            if k == "action" and v not in VALID_ACTIONS:
                raise HTTPException(400, f"Unknown action: {v}")
            setattr(r, k, v)
    await record_admin(session, org_id=principal.org_id,
                       actor=f"user:{principal.email}",
                       event_type="guardrail.rule.updated",
                       resource_type="guardrail_rule", resource_id=rule_id,
                       payload=body)
    await session.commit()
    return RuleOut.from_orm(r)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    _require_admin(principal)
    r = await session.get(GuardrailRule, uuid.UUID(rule_id))
    if not r or str(r.organization_id) != principal.org_id:
        raise HTTPException(404, "Rule not found")
    await session.delete(r)
    await session.commit()


# ── Inbound event schema (stable API contract) ────────────────────────────────

@router.get("/event-schema")
async def get_event_schema(_: Principal = Depends(get_principal)):
    """
    Return the stable Kynara inbound event API contract.

    Configure your monitoring platform's webhook to POST this JSON to
    /api/v1/guardrails/inbound/{integration_id}.

    Kynara's format never changes to match provider-specific formats —
    instead each platform uses its own webhook templating to produce this
    shape. Provider-specific template snippets are returned alongside the schema.
    """
    return {
        "schema": {
            "agent_id": {
                "type": "string",
                "required": True,
                "description": "Kynara agent UUID or slug. Identifies which agent this event targets.",
                "example": "3f8a2b1c-0000-0000-0000-000000000001",
            },
            "rule_name": {
                "type": "string",
                "required": True,
                "description": "Name of the alert / check that fired.",
                "example": "high_error_rate",
            },
            "severity": {
                "type": "string",
                "required": True,
                "enum": ["critical", "warning", "info"],
                "description": "Severity level of the event.",
                "example": "critical",
            },
            "score": {
                "type": "number",
                "required": False,
                "description": "Optional numeric score (0–1) from the monitoring platform.",
                "example": 0.95,
            },
            "trace_id": {
                "type": "string",
                "required": False,
                "description": "Optional trace or incident ID for cross-referencing.",
                "example": "trace-abc123",
            },
            "message": {
                "type": "string",
                "required": False,
                "description": "Human-readable description of the event.",
                "example": "Error rate exceeded 5% threshold for 3 consecutive minutes.",
            },
        },
        "example_payload": {
            "agent_id": "3f8a2b1c-0000-0000-0000-000000000001",
            "rule_name": "high_error_rate",
            "severity": "critical",
            "score": 0.95,
            "trace_id": "trace-abc123",
            "message": "Error rate exceeded 5% threshold for 3 consecutive minutes.",
        },
        "provider_templates": {
            "grafana": {
                "description": (
                    "In Grafana → Alerting → Notification templates, create a template named 'kynara'. "
                    "Then in your Webhook contact point set Message to: {{ template \"kynara\" . }}"
                ),
                "notification_template": (
                    "{{ define \"kynara\" -}}\n"
                    "{\n"
                    "  \"agent_id\": \"{{ .CommonLabels.kynara_agent_id }}\",\n"
                    "  \"rule_name\": \"{{ .CommonLabels.alertname }}\",\n"
                    "  \"severity\": \"{{ if .CommonLabels.severity }}{{ .CommonLabels.severity }}{{ else }}critical{{ end }}\",\n"
                    "  \"message\": \"{{ .CommonAnnotations.summary }}\"\n"
                    "}\n"
                    "{{- end }}"
                ),
                "alert_label_instructions": (
                    "Add the label kynara_agent_id=<agent-uuid> and severity=critical|warning|info "
                    "to each Grafana alert rule that should target a Kynara agent."
                ),
            },
            "datadog": {
                "description": (
                    "In Datadog → Integrations → Webhooks, create a webhook and set the custom payload below."
                ),
                "custom_payload": (
                    "{\n"
                    "  \"agent_id\": \"$kynara_agent_id\",\n"
                    "  \"rule_name\": \"$alert_title\",\n"
                    "  \"severity\": \"$alert_type\",\n"
                    "  \"score\": \"$alert_metric\",\n"
                    "  \"trace_id\": \"$id\",\n"
                    "  \"message\": \"$text_only_msg\"\n"
                    "}"
                ),
                "tag_instructions": (
                    "Tag your Datadog monitor with kynara_agent_id:<agent-uuid> so the $kynara_agent_id "
                    "variable is populated. Use @webhook-<name> in the monitor message to trigger it."
                ),
            },
            "pagerduty": {
                "description": (
                    "PagerDuty supports outbound webhooks via Event Orchestration or generic v3 webhooks. "
                    "Use a middleware (e.g. AWS Lambda or a small Cloud Function) to translate "
                    "PagerDuty's incident payload to Kynara's format and forward it."
                ),
                "suggested_lambda": (
                    "import json, urllib.request\n\n"
                    "KYNARA_URL = 'https://app.kynara.com/api/v1/guardrails/inbound/<integration_id>'\n\n"
                    "def handler(event, context):\n"
                    "    pd = json.loads(event['body'])\n"
                    "    incident = pd['messages'][0]['incident']\n"
                    "    payload = {\n"
                    "        'agent_id': incident.get('custom_fields', {}).get('kynara_agent_id'),\n"
                    "        'rule_name': incident.get('title', 'unknown'),\n"
                    "        'severity': 'critical' if incident.get('urgency') == 'high' else 'warning',\n"
                    "        'trace_id': incident.get('id'),\n"
                    "        'message': incident.get('summary'),\n"
                    "    }\n"
                    "    req = urllib.request.Request(KYNARA_URL, json.dumps(payload).encode(), \n"
                    "        {'Content-Type': 'application/json'}, method='POST')\n"
                    "    urllib.request.urlopen(req)\n"
                    "    return {'statusCode': 200}"
                ),
            },
            "prometheus": {
                "description": (
                    "Prometheus Alertmanager does not support custom webhook bodies natively. "
                    "Run a small alertmanager-webhook-adapter sidecar, or use the template below "
                    "with alertmanager's webhook_configs and a reverse proxy that reshapes the body."
                ),
                "alertmanager_yaml": (
                    "receivers:\n"
                    "  - name: kynara\n"
                    "    webhook_configs:\n"
                    "      - url: 'https://app.kynara.com/api/v1/guardrails/inbound/<integration_id>'\n"
                    "        send_resolved: false\n"
                    "        http_config:\n"
                    "          headers:\n"
                    "            Content-Type: application/json\n"
                    "        # Use a proxy/adapter to reshape Alertmanager's payload to Kynara's format\n"
                    "        # Required fields: agent_id, rule_name, severity"
                ),
                "adapter_note": (
                    "A minimal adapter maps: labels.kynara_agent_id → agent_id, "
                    "labels.alertname → rule_name, labels.severity → severity."
                ),
            },
            "newrelic": {
                "description": (
                    "In New Relic → Alerts → Notification channels, add a Webhook channel. "
                    "Set the custom payload JSON below under 'Custom Headers / Payload'."
                ),
                "custom_payload": (
                    "{\n"
                    "  \"agent_id\": \"{{ $labels.kynara_agent_id }}\",\n"
                    "  \"rule_name\": \"{{ $labels.conditionName }}\",\n"
                    "  \"severity\": \"{{ $labels.priority }}\",\n"
                    "  \"score\": {{ $value }},\n"
                    "  \"trace_id\": \"{{ $labels.incidentId }}\",\n"
                    "  \"message\": \"{{ $labels.conditionDescription }}\"\n"
                    "}"
                ),
            },
        },
    }


# ── Events list ───────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[GuardrailEventOut])
async def list_events(
    limit: int = 50,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_db),
):
    rows = (await session.scalars(
        select(GuardrailEvent)
        .where(GuardrailEvent.organization_id == uuid.UUID(principal.org_id))
        .order_by(GuardrailEvent.created_at.desc())
        .limit(limit)
    )).all()
    return [GuardrailEventOut.from_orm(e) for e in rows]


# ── Enforcement ───────────────────────────────────────────────────────────────

async def _enforce_action(
    session: AsyncSession,
    org_id: str,
    agent: Agent | None,
    action: str,
    event: GuardrailEvent,
    triggered_by: str = "rule",
) -> dict[str, Any]:
    """Apply the enforcement action and return a detail dict."""
    detail: dict[str, Any] = {"action": action, "triggered_by": triggered_by}

    if action == "alert_only" or agent is None:
        return detail

    if action in ("suspend_agent", "disable_agent"):
        agent.is_active = False
        detail["disabled"] = True
        await record_admin(session, org_id=org_id, actor="system:guardrail",
                           event_type="guardrail.agent.disabled",
                           resource_type="agent", resource_id=str(agent.id),
                           payload={"rule": event.rule_name, "severity": event.severity,
                                    "triggered_by": triggered_by})

    elif action == "revoke_jit_grants":
        grants = (await session.scalars(
            select(JitGrant).where(
                JitGrant.organization_id == uuid.UUID(org_id),
                JitGrant.user_id == agent.id,
                JitGrant.is_active.is_(True),
                JitGrant.expires_at > datetime.now(timezone.utc),
            )
        )).all()
        for g in grants:
            g.is_active = False
            g.revoked_at = datetime.now(timezone.utc)
        detail["jit_grants_revoked"] = len(grants)
        await record_admin(session, org_id=org_id, actor="system:guardrail",
                           event_type="guardrail.jit_grants.revoked",
                           resource_type="agent", resource_id=str(agent.id),
                           payload={"count": len(grants), "rule": event.rule_name,
                                    "triggered_by": triggered_by})

    elif action in ("deny_all_policy", "reduce_to_readonly"):
        slug = f"guardrail-auto-{action}-{agent.slug}"
        actions_denied = ["*"] if action == "deny_all_policy" else [
            "*.write", "*.update", "*.delete", "*.create"]
        existing = (await session.scalars(
            select(Policy).where(
                Policy.organization_id == uuid.UUID(org_id),
                Policy.slug == slug,
            )
        )).first()
        if not existing:
            p = Policy(
                organization_id=uuid.UUID(org_id),
                slug=slug,
                display_name=f"[GUARDRAIL] {action} — {agent.slug}",
                description=f"Auto-created by guardrail: {event.rule_name}",
                effect="deny",
                priority=1,
                actions=actions_denied,
                resource_types=[],
                condition={"op": "eq", "args": ["ctx.subject.id", str(agent.id)]},
                is_enabled=True,
            )
            session.add(p)
            detail["policy_created"] = slug
        else:
            existing.is_enabled = True
            detail["policy_reenabled"] = slug
        await record_admin(session, org_id=org_id, actor="system:guardrail",
                           event_type="guardrail.policy.injected",
                           resource_type="agent", resource_id=str(agent.id),
                           payload={"policy": slug, "rule": event.rule_name,
                                    "triggered_by": triggered_by})
    return detail


async def _evaluate_rules(
    session: AsyncSession,
    org_id: str,
    integration_id: uuid.UUID,
    agent: Agent | None,
    event: GuardrailEvent,
) -> list[dict[str, Any]]:
    """
    Check all enabled GuardrailRules for this org.
    For each matching rule, count how many GuardrailEvents (including the
    one just recorded) fall within the rule's time window.
    If count >= threshold, enforce the rule's action.
    Returns a list of enforcement detail dicts for every rule that fired.
    """
    rules = (await session.scalars(
        select(GuardrailRule).where(
            GuardrailRule.organization_id == uuid.UUID(org_id),
            GuardrailRule.is_enabled.is_(True),
        )
    )).all()

    fired: list[dict[str, Any]] = []

    for rule in rules:
        # Filter: integration scope
        if rule.integration_id and rule.integration_id != integration_id:
            continue

        # Filter: agent
        if rule.filter_agent_ids and agent:
            if agent.id not in rule.filter_agent_ids:
                continue
        elif rule.filter_agent_ids and not agent:
            continue  # rule requires a specific agent but we have none

        # Filter: severity
        if rule.filter_severities and event.severity not in rule.filter_severities:
            continue

        # Filter: rule_name
        if rule.filter_rule_names and event.rule_name not in rule.filter_rule_names:
            continue

        # Count matching events in the time window
        window_start = datetime.now(timezone.utc) - timedelta(seconds=rule.time_window_seconds)

        count_q = select(func.count()).select_from(GuardrailEvent).where(
            GuardrailEvent.organization_id == uuid.UUID(org_id),
            GuardrailEvent.created_at >= window_start,
        )
        # Narrow by agent if rule has agent filter
        if rule.filter_agent_ids and agent:
            count_q = count_q.where(GuardrailEvent.agent_id == agent.id)
        # Narrow by severity if rule has severity filter
        if rule.filter_severities:
            count_q = count_q.where(GuardrailEvent.severity.in_(rule.filter_severities))
        # Narrow by rule_name if rule has rule_name filter
        if rule.filter_rule_names:
            count_q = count_q.where(GuardrailEvent.rule_name.in_(rule.filter_rule_names))

        event_count = await session.scalar(count_q) or 0

        if event_count >= rule.event_count_threshold:
            detail = await _enforce_action(
                session, org_id, agent, rule.action, event,
                triggered_by=f"rule:{rule.id}:{rule.name}",
            )
            detail["rule_id"] = str(rule.id)
            detail["rule_name"] = rule.name
            detail["event_count"] = event_count
            detail["threshold"] = rule.event_count_threshold
            detail["window_seconds"] = rule.time_window_seconds
            fired.append(detail)

    return fired


# ── Inbound webhook ───────────────────────────────────────────────────────────

@router.post("/inbound/{integration_id}", include_in_schema=True)
async def inbound_guardrail_event(
    integration_id: str,
    request: Request,
    session: AsyncSession = Depends(_db),
    x_kynara_signature: str | None = Header(None),
    x_arize_signature: str | None = Header(None),
):
    """
    Receive a guardrail violation webhook from Arize, Langfuse,
    WhyLabs, Fiddler, or a custom platform.

    Expected minimum payload:
      {
        "agent_id":  "<agent UUID or slug>",
        "rule_name": "toxicity_check",
        "severity":  "critical",
        "score":     0.92,
        "trace_id":  "..."
      }

    After recording the event, Kynara evaluates all enabled GuardrailRules
    for this org. Each rule fires when the event count within its time window
    reaches its threshold — e.g. "suspend agent after 5 critical events in
    5 minutes". Rules without a threshold (event_count_threshold=1) fire
    immediately on every matching event, equivalent to the old behaviour.
    """
    raw_body = await request.body()
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    integration = await session.get(GuardrailIntegration, uuid.UUID(integration_id))
    if not integration or not integration.is_enabled:
        raise HTTPException(404, "Integration not found or disabled")

    org_id = str(integration.organization_id)

    # HMAC verification (F-14: always use constant-time comparison)
    sig = x_kynara_signature or x_arize_signature
    if integration.webhook_secret_hash:
        if not sig:
            raise HTTPException(401, "Missing signature header")
        # Compute expected hash and compare in constant time to prevent timing attacks
        expected_hash = hash_token(sig)
        if not hmac.compare_digest(expected_hash, integration.webhook_secret_hash):
            raise HTTPException(401, "Invalid signature")
    elif not sig:
        # Log a warning when no secret is configured (F-02: unauthenticated inbound webhooks)
        from app.core.logging import get_logger as _get_logger
        _get_logger("kynara.guardrails").warning(
            "guardrail.inbound.no_secret",
            integration_id=str(integration_id),
            msg="Integration has no webhook_secret configured — inbound events are unauthenticated. "
                "Set webhook_secret when creating/updating the integration.",
        )

    # Normalise fields across providers
    agent_ref: str | None = (
        body.get("agent_id") or body.get("agentId")
        or body.get("model_id") or body.get("model")
    )
    rule_name: str = (
        body.get("rule_name") or body.get("ruleName")
        or body.get("check_name") or body.get("monitor_name") or "unknown"
    )
    severity: str = str(body.get("severity") or body.get("level") or "warning").lower()

    if integration.monitored_rules and rule_name not in integration.monitored_rules:
        return {"status": "ignored", "reason": "rule not monitored"}

    # Resolve agent
    agent: Agent | None = None
    if agent_ref:
        try:
            agent = await session.get(Agent, uuid.UUID(agent_ref))
        except (ValueError, AttributeError):
            agent = (await session.scalars(
                select(Agent).where(
                    Agent.organization_id == uuid.UUID(org_id),
                    Agent.slug == agent_ref,
                )
            )).first()

    if integration.agent_ids and agent and agent.id not in integration.agent_ids:
        return {"status": "ignored", "reason": "agent not monitored"}

    # Record the raw event (action_taken will be updated after rule evaluation)
    ev = GuardrailEvent(
        organization_id=uuid.UUID(org_id),
        integration_id=integration.id,
        agent_id=agent.id if agent else None,
        rule_name=rule_name,
        severity=severity,
        payload=body,
        action_taken="pending",
        action_detail={},
    )
    session.add(ev)
    await session.flush()  # get ev.id without committing

    # Evaluate threshold rules
    fired_rules = await _evaluate_rules(
        session, org_id, integration.id, agent, ev)

    if fired_rules:
        # Use the most severe action taken across all fired rules
        ACTION_RANK = ["alert_only", "reduce_to_readonly",
                       "revoke_jit_grants", "deny_all_policy", "disable_agent", "suspend_agent"]
        top_action = max(
            (d["action"] for d in fired_rules),
            key=lambda a: ACTION_RANK.index(a) if a in ACTION_RANK else -1,
        )
        ev.action_taken = top_action
        ev.action_detail = {"rules_fired": fired_rules}
    else:
        # No rules configured or none matched — record as alert_only
        ev.action_taken = "alert_only"
        ev.action_detail = {"reason": "no matching rules"}

    await record_admin(session, org_id=org_id, actor="system:guardrail",
                       event_type="guardrail.event.received",
                       resource_type="guardrail_event", resource_id=str(ev.id),
                       payload={"rule": rule_name, "severity": severity,
                                "action": ev.action_taken,
                                "rules_fired": len(fired_rules),
                                "agent": str(agent.id) if agent else None})
    await emit(session, org_id, "guardrail.triggered", {
        "event_id": str(ev.id),
        "rule_name": rule_name,
        "severity": severity,
        "action_taken": ev.action_taken,
        "rules_fired": fired_rules,
        "agent_id": str(agent.id) if agent else None,
    })
    await session.commit()
    return {
        "status": "ok",
        "event_id": str(ev.id),
        "action_taken": ev.action_taken,
        "rules_fired": len(fired_rules),
        "detail": ev.action_detail,
    }
