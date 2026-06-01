"""Per-org integration configuration endpoints.

GET  /api/v1/integrations/config          → returns current settings (tokens masked)
PUT  /api/v1/integrations/config          → upsert Slack/Teams config for this org
POST /api/v1/integrations/config/test     → send a test notification to verify setup
DELETE /api/v1/integrations/config/slack  → remove Slack config for this org
DELETE /api/v1/integrations/config/teams  → remove Teams config for this org

Only org owners and admins can access these endpoints.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, require_seat
from app.core.encryption import decrypt, encrypt
from app.db.session import SessionLocal
from app.models.org_integration import OrgIntegration

router = APIRouter(prefix="/integrations/config", tags=["integrations"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _mask(value: str | None) -> str | None:
    """Return a masked version — show only the last 4 chars."""
    if not value:
        return None
    plain = decrypt(value)
    if len(plain) <= 8:
        return "****"
    return "****" + plain[-4:]


# ── Schemas ───────────────────────────────────────────────────────────────────

class SlackConfigIn(BaseModel):
    bot_token: str | None = None          # xoxb-... (preferred)
    signing_secret: str | None = None
    channel_id: str | None = None
    webhook_url: str | None = None        # alternative to bot token
    enabled: bool = True


class TeamsConfigIn(BaseModel):
    webhook_url: str                       # Teams Incoming Webhook URL
    callback_secret: str | None = None    # for Power Automate HMAC verification
    enabled: bool = True


class PagerDutyConfigIn(BaseModel):
    routing_key: str
    enabled: bool = True


class EmailConfigIn(BaseModel):
    recipients: str  # comma-separated email addresses
    enabled: bool = True


class IntegrationConfigIn(BaseModel):
    slack: SlackConfigIn | None = None
    teams: TeamsConfigIn | None = None
    pagerduty: PagerDutyConfigIn | None = None
    email: EmailConfigIn | None = None


class IntegrationConfigOut(BaseModel):
    slack_enabled: bool
    slack_channel_id: str | None
    slack_bot_token_set: bool
    slack_signing_secret_set: bool
    slack_webhook_url_set: bool

    teams_enabled: bool
    teams_webhook_url_set: bool
    teams_callback_secret_set: bool

    pagerduty_enabled: bool
    pagerduty_routing_key_set: bool

    email_enabled: bool
    email_recipients: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_create(session: AsyncSession, org_id: str) -> OrgIntegration:
    row = await session.scalar(
        select(OrgIntegration).where(
            OrgIntegration.organization_id == uuid.UUID(org_id)
        )
    )
    if not row:
        row = OrgIntegration(organization_id=uuid.UUID(org_id))
        session.add(row)
        await session.flush()
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=IntegrationConfigOut)
async def get_config(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Return current integration settings for this org (sensitive values masked)."""
    row = await session.scalar(
        select(OrgIntegration).where(
            OrgIntegration.organization_id == uuid.UUID(principal.org_id)
        )
    )
    if not row:
        return IntegrationConfigOut(
            slack_enabled=False, slack_channel_id=None,
            slack_bot_token_set=False, slack_signing_secret_set=False, slack_webhook_url_set=False,
            teams_enabled=False, teams_webhook_url_set=False, teams_callback_secret_set=False,
            pagerduty_enabled=False, pagerduty_routing_key_set=False,
            email_enabled=False, email_recipients=None,
        )
    return IntegrationConfigOut(
        slack_enabled=row.slack_enabled,
        slack_channel_id=row.slack_channel_id,
        slack_bot_token_set=bool(row.slack_bot_token_enc),
        slack_signing_secret_set=bool(row.slack_signing_secret_enc),
        slack_webhook_url_set=bool(row.slack_webhook_url_enc),
        teams_enabled=row.teams_enabled,
        teams_webhook_url_set=bool(row.teams_webhook_url_enc),
        teams_callback_secret_set=bool(row.teams_callback_secret_enc),
        pagerduty_enabled=row.pagerduty_enabled,
        pagerduty_routing_key_set=bool(row.pagerduty_routing_key_enc),
        email_enabled=row.approval_email_enabled,
        email_recipients=row.approval_email_to,
    )


@router.put("", response_model=IntegrationConfigOut)
async def upsert_config(
    body: IntegrationConfigIn,
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Save Slack and/or Teams integration settings for this org."""
    row = await _get_or_create(session, principal.org_id)

    if body.slack is not None:
        s = body.slack
        if s.bot_token:
            row.slack_bot_token_enc = encrypt(s.bot_token)
        if s.signing_secret:
            row.slack_signing_secret_enc = encrypt(s.signing_secret)
        if s.channel_id:
            row.slack_channel_id = s.channel_id
        if s.webhook_url:
            row.slack_webhook_url_enc = encrypt(s.webhook_url)
        row.slack_enabled = s.enabled

    if body.teams is not None:
        t = body.teams
        row.teams_webhook_url_enc = encrypt(t.webhook_url)
        if t.callback_secret:
            row.teams_callback_secret_enc = encrypt(t.callback_secret)
        row.teams_enabled = t.enabled

    if body.pagerduty is not None:
        row.pagerduty_routing_key_enc = encrypt(body.pagerduty.routing_key)
        row.pagerduty_enabled = body.pagerduty.enabled

    if body.email is not None:
        row.approval_email_to = body.email.recipients
        row.approval_email_enabled = body.email.enabled

    await session.commit()

    return IntegrationConfigOut(
        slack_enabled=row.slack_enabled,
        slack_channel_id=row.slack_channel_id,
        slack_bot_token_set=bool(row.slack_bot_token_enc),
        slack_signing_secret_set=bool(row.slack_signing_secret_enc),
        slack_webhook_url_set=bool(row.slack_webhook_url_enc),
        teams_enabled=row.teams_enabled,
        teams_webhook_url_set=bool(row.teams_webhook_url_enc),
        teams_callback_secret_set=bool(row.teams_callback_secret_enc),
        pagerduty_enabled=row.pagerduty_enabled,
        pagerduty_routing_key_set=bool(row.pagerduty_routing_key_enc),
        email_enabled=row.approval_email_enabled,
        email_recipients=row.approval_email_to,
    )


@router.post("/test")
async def test_integration(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    """Send a test notification to verify Slack/Teams config."""
    from datetime import datetime, timedelta, timezone
    from app.integrations.slack import post_approval_message as slack_post
    from app.integrations.teams import post_approval_card as teams_post
    from app.models.org_integration import OrgIntegration

    row = await session.scalar(
        select(OrgIntegration).where(
            OrgIntegration.organization_id == uuid.UUID(principal.org_id)
        )
    )

    results = {}
    test_expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    test_kwargs = dict(
        approval_id="test-00000000",
        subject_id="test-agent",
        action="test.notification",
        resource_type="test",
        resource_id="test-resource",
        resource_attrs={},
        policy_name="Test policy — verify integration",
        expires_at=test_expires,
        context={},
    )

    if row and row.slack_enabled and (row.slack_bot_token_enc or row.slack_webhook_url_enc):
        ts = await slack_post(**test_kwargs, _org_integration=row)
        results["slack"] = "ok" if ts else "failed"
    else:
        results["slack"] = "not_configured"

    if row and row.teams_enabled and row.teams_webhook_url_enc:
        ok = await teams_post(**{k: v for k, v in test_kwargs.items() if k != "context"}, _org_integration=row)
        results["teams"] = "ok" if ok else "failed"
    else:
        results["teams"] = "not_configured"

    return results


@router.delete("/slack", status_code=204)
async def delete_slack_config(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    row = await session.scalar(
        select(OrgIntegration).where(
            OrgIntegration.organization_id == uuid.UUID(principal.org_id)
        )
    )
    if row:
        row.slack_bot_token_enc = None
        row.slack_signing_secret_enc = None
        row.slack_webhook_url_enc = None
        row.slack_channel_id = None
        row.slack_enabled = False
        await session.commit()


@router.delete("/teams", status_code=204)
async def delete_teams_config(
    principal: Principal = Depends(require_seat("owner", "admin")),
    session: AsyncSession = Depends(_session),
):
    row = await session.scalar(
        select(OrgIntegration).where(
            OrgIntegration.organization_id == uuid.UUID(principal.org_id)
        )
    )
    if row:
        row.teams_webhook_url_enc = None
        row.teams_callback_secret_enc = None
        row.teams_enabled = False
        await session.commit()
