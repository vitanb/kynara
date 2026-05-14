"""Decision check endpoint — the hot path SDK calls flow through."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal, require_scope
from app.billing.quota import enforce_decision_quota, record_decision
from app.core.geoip import resolve_country
from app.db.session import SessionLocal
from app.policy.service import decide

router = APIRouter(prefix="/decisions", tags=["decisions"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _is_uuid(v: str) -> bool:
    try:
        _uuid.UUID(v)
        return True
    except (ValueError, AttributeError):
        return False


class DecisionIn(BaseModel):
    subject_type: str = Field(pattern=r"^(agent|user|api_key)$")
    subject_id: str
    on_behalf_of_user_id: str | None = None
    action: str
    resource: dict = Field(default_factory=lambda: {"type": None, "id": None, "attrs": {}})
    context: dict = Field(default_factory=dict)

    @field_validator("subject_id")
    @classmethod
    def subject_id_must_be_uuid(cls, v: str) -> str:
        if not _is_uuid(v):
            raise ValueError(
                f"subject_id must be a UUID (got {v!r}). "
                "Use the agent/user/api_key ID from the Kynara UI, not a slug or email."
            )
        return v

    @field_validator("on_behalf_of_user_id")
    @classmethod
    def on_behalf_must_be_uuid(cls, v: str | None) -> str | None:
        if v is not None and not _is_uuid(v):
            raise ValueError(
                f"on_behalf_of_user_id must be a UUID (got {v!r}). "
                "Use the user ID from Settings → Members."
            )
        return v


class DecisionOut(BaseModel):
    effect: str
    reason: str
    matched_policy_id: str | None
    obligations: list[dict]
    approval_id: str | None = None       # set when effect == "require_approval"
    granted_scopes: list[str] = []       # diagnostic: scopes the subject held at decision time
    rbac_pass: bool = True               # False when denied at the RBAC gate before ABAC ran


@router.post("/check", response_model=DecisionOut)
async def check(
    body: DecisionIn, request: Request,
    principal: Principal = Depends(require_scope("decisions.check")),
    session: AsyncSession = Depends(_session),
):
    # Enforce monthly quota before processing — returns 402 when exhausted
    await enforce_decision_quota(session, principal.org_id)

    client_ip = request.client.host if request.client else None
    # Resolve country from IP — cached in Redis, never blocks on failure.
    # Callers may override by passing ip_country in context explicitly.
    ip_country = body.context.get("ip_country") or await resolve_country(client_ip)
    ctx = {
        **body.context,
        "time": datetime.now(tz=timezone.utc).isoformat(),
        "ip": client_ip,
        "ip_country": ip_country,
        "request_id": request.headers.get("x-request-id"),
    }
    d = await decide(
        session,
        org_id=principal.org_id,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        on_behalf_of_user_id=body.on_behalf_of_user_id,
        action=body.action,
        resource=body.resource,
        context=ctx,
    )
    # Record usage (non-fatal — quota check already ran above)
    agent_id = body.subject_id if body.subject_type == "agent" else None
    await record_decision(session, principal.org_id, d.effect, agent_id=agent_id)
    await session.commit()

    return DecisionOut(
        effect=d.effect,
        reason=d.reason,
        matched_policy_id=d.matched_policy_id,
        obligations=d.obligations,
        approval_id=getattr(d, "approval_id", None),
        granted_scopes=d.granted_scopes,
        rbac_pass=d.rbac_pass,
    )
