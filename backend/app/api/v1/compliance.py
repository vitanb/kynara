"""Compliance evidence — maps this org's live Kynara configuration to named
security controls from OWASP AI Exchange, MITRE ATLAS, ISO/IEC 42001/27002,
and the EU AI Act.

Unlike a static compliance page, every control's status is *derived from the
org's actual configuration* (policies, roles, approvals, audit chain, budgets)
at request time — so the export is evidence, not aspiration.

GET /api/v1/compliance/evidence
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import Principal, get_principal
from app.db.session import SessionLocal
from app.models import (
    Agent,
    AgentAssignment,
    ApprovalRequest,
    AuditEvent,
    Policy,
    RolePermission,
    Role,
)
from app.models.jit_grant import JitGrant

router = APIRouter(prefix="/compliance", tags=["compliance"])


async def _session():
    async with SessionLocal() as s:
        yield s


def _control(
    control_id: str,
    name: str,
    frameworks: list[dict],
    status: str,
    evidence: dict,
    how: str,
) -> dict:
    return {
        "id": control_id,
        "name": name,
        "frameworks": frameworks,
        "status": status,  # implemented | partial | not_configured
        "evidence": evidence,
        "how_kynara_implements": how,
    }


@router.get("/evidence")
async def compliance_evidence(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(_session),
):
    org = uuid.UUID(principal.org_id)

    # ── Gather live configuration ───────────────────────────────────────────
    policies = (await session.scalars(
        select(Policy).where(Policy.organization_id == org, Policy.is_enabled.is_(True))
    )).all()
    n_roles = (await session.scalar(
        select(func.count()).select_from(Role).where(Role.organization_id == org)
    )) or 0
    scoped_grants = (await session.scalar(
        select(func.count()).select_from(RolePermission)
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.organization_id == org, RolePermission.scope != "*")
    )) or 0
    agents = (await session.scalars(
        select(Agent).where(Agent.organization_id == org)
    )).all()
    n_assignments = (await session.scalar(
        select(func.count()).select_from(AgentAssignment)
        .where(AgentAssignment.organization_id == org, AgentAssignment.is_active.is_(True))
    )) or 0
    n_audit = (await session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.organization_id == org)
    )) or 0
    approvals_resolved = (await session.scalar(
        select(func.count()).select_from(ApprovalRequest).where(
            ApprovalRequest.organization_id == org,
            ApprovalRequest.status.in_(("approved", "rejected")),
        )
    )) or 0
    approvals_total = (await session.scalar(
        select(func.count()).select_from(ApprovalRequest)
        .where(ApprovalRequest.organization_id == org)
    )) or 0
    n_jit = (await session.scalar(
        select(func.count()).select_from(JitGrant).where(JitGrant.organization_id == org)
    )) or 0

    def policies_using(marker: str) -> list[dict]:
        out = []
        for p in policies:
            try:
                if marker in json.dumps(p.condition or {}) or marker == p.effect:
                    out.append({"id": str(p.id), "name": p.display_name})
            except (TypeError, ValueError):
                continue
        return out

    approval_policies = policies_using("require_approval")
    taint_policies = policies_using("is_tainted")
    sequence_policies = policies_using("preceded_by")
    budgeted_agents = [a for a in agents if (a.daily_action_budget or 0) > 0]

    def status_of(implemented: bool, partial: bool = False) -> str:
        return "implemented" if implemented else "partial" if partial else "not_configured"

    controls = [
        _control(
            "least-privilege",
            "Least model privilege (task-scoped agent permissions)",
            [
                {"framework": "OWASP AI Exchange", "ref": "#LEAST MODEL PRIVILEGE", "url": "https://owaspai.org/go/leastmodelprivilege/"},
                {"framework": "MITRE ATLAS", "ref": "AML.M0028", "url": "https://atlas.mitre.org/mitigations/AML.M0028"},
                {"framework": "ISO/IEC 27002", "ref": "8.2 Privileged access rights"},
            ],
            status_of(n_roles > 0 and scoped_grants > 0, n_roles > 0),
            {"roles": n_roles, "scoped_grants": scoped_grants,
             "agents": len(agents), "active_assignments": n_assignments},
            "Agents receive only role-granted scopes; the RBAC gate denies any "
            "action outside the grant set before policy evaluation (fail-closed).",
        ),
        _control(
            "human-oversight",
            "Human-in-the-loop approval for high-risk actions",
            [
                {"framework": "OWASP AI Exchange", "ref": "#OVERSIGHT", "url": "https://owaspai.org/go/oversight/"},
                {"framework": "MITRE ATLAS", "ref": "AML.M0029", "url": "https://atlas.mitre.org/mitigations/AML.M0029"},
                {"framework": "ISO/IEC 42001", "ref": "B.9.3 Human oversight"},
                {"framework": "EU AI Act", "ref": "Art. 14 Human oversight"},
            ],
            status_of(len(approval_policies) > 0),
            {"require_approval_policies": approval_policies,
             "approvals_resolved": approvals_resolved, "approvals_total": approvals_total},
            "Policies return require_approval; the agent pauses until a human "
            "approves or rejects with a mandatory audit-logged justification.",
        ),
        _control(
            "untrusted-input-downgrade",
            "Permission downgrade on untrusted input (taint tracking)",
            [
                {"framework": "OWASP AI Exchange", "ref": "#LEAST MODEL PRIVILEGE — risk elevation", "url": "https://owaspai.org/go/leastmodelprivilege/"},
                {"framework": "MITRE ATLAS", "ref": "AML.M0030", "url": "https://atlas.mitre.org/mitigations/AML.M0030"},
            ],
            status_of(len(taint_policies) > 0),
            {"is_tainted_policies": taint_policies},
            "The is_tainted condition tightens permissions the moment an agent "
            "ingests untrusted content; decided outside the model, so prompt "
            "injection cannot lift the restriction.",
        ),
        _control(
            "workflow-integrity",
            "Workflow-order enforcement (sequence policies)",
            [
                {"framework": "OWASP AI Exchange", "ref": "#OVERSIGHT — rule-based sanity checks during steps", "url": "https://owaspai.org/go/oversight/"},
                {"framework": "MITRE ATLAS", "ref": "AML.M0029/M0030"},
            ],
            status_of(len(sequence_policies) > 0),
            {"preceded_by_policies": sequence_policies},
            "preceded_by conditions require a prior allowed action in the same "
            "session (e.g. verification before refund), defending against "
            "application-flow perturbation by manipulated agents.",
        ),
        _control(
            "non-escalation",
            "Delegation non-escalation (agent ≤ dispatching user)",
            [
                {"framework": "OWASP AI Exchange", "ref": "#LEAST MODEL PRIVILEGE — honor limitations of the served", "url": "https://owaspai.org/go/leastmodelprivilege/"},
                {"framework": "MITRE ATLAS", "ref": "AML.M0027", "url": "https://atlas.mitre.org/mitigations/AML.M0027"},
            ],
            status_of(n_assignments > 0),
            {"active_assignments": n_assignments},
            "For delegated requests the effective scope set is the intersection "
            "of the agent's role grants and the dispatching user's grants — an "
            "agent can never exceed the human it acts for.",
        ),
        _control(
            "resource-budgets",
            "Action budgets / resource exhaustion limits",
            [
                {"framework": "OWASP AI Exchange", "ref": "Exhaustion threats", "url": "https://owaspai.org/go/airesourceexhaustion/"},
                {"framework": "MITRE ATLAS", "ref": "AML.M0026", "url": "https://atlas.mitre.org/mitigations/AML.M0026"},
            ],
            status_of(len(budgeted_agents) == len(agents) and len(agents) > 0,
                      len(budgeted_agents) > 0),
            {"agents_with_budget": len(budgeted_agents), "agents_total": len(agents)},
            "Every agent carries a daily action budget enforced as a hard gate "
            "before policy evaluation; exhaustion returns deny.",
        ),
        _control(
            "ephemeral-permissions",
            "Ephemeral / just-in-time permission elevation",
            [
                {"framework": "OWASP AI Exchange", "ref": "#LEAST MODEL PRIVILEGE — ephemeral permissions", "url": "https://owaspai.org/go/leastmodelprivilege/"},
            ],
            status_of(n_jit > 0, True),
            {"jit_grants_recorded": n_jit},
            "JIT grants give time-boxed scope elevations with justification and "
            "ticket link; expiry and revocation land in the audit chain.",
        ),
        _control(
            "tamper-evident-records",
            "Tamper-evident decision records",
            [
                {"framework": "ISO/IEC 42001", "ref": "Record keeping"},
                {"framework": "EU AI Act", "ref": "Art. 12 Record-keeping / logging"},
                {"framework": "SOC 2", "ref": "CC7.2 monitoring evidence"},
            ],
            status_of(n_audit > 0),
            {"audit_events": n_audit, "chain": "SHA-256 hash-chained, verify at POST /api/v1/audit/verify"},
            "Every decision (allow, deny, require_approval) is appended to a "
            "per-org SHA-256 hash chain; retroactive edits break the chain and "
            "are detectable by independent re-computation.",
        ),
        _control(
            "kill-switch",
            "Emergency halt (agent kill switch)",
            [
                {"framework": "OWASP AI Exchange", "ref": "#OVERSIGHT — halting execution", "url": "https://owaspai.org/go/oversight/"},
                {"framework": "EU AI Act", "ref": "Art. 14(4)(e) — intervene or interrupt"},
            ],
            status_of(len(agents) > 0),
            {"agents": len(agents),
             "disabled_agents": sum(1 for a in agents if not a.is_active)},
            "Any agent can be disabled instantly; all subsequent decision "
            "requests return deny until an admin re-enables it (itself audited).",
        ),
        _control(
            "oversight-fatigue-monitoring",
            "Approval-fatigue monitoring of human oversight",
            [
                {"framework": "OWASP AI Exchange", "ref": "#OVERSIGHT — limitations of human oversight", "url": "https://owaspai.org/go/oversight/"},
            ],
            status_of(approvals_resolved > 0, True),
            {"approvals_resolved": approvals_resolved,
             "analytics": "GET /api/v1/approvals/analytics (rubber-stamp, speed, overload signals)"},
            "Kynara monitors per-approver volume, approve-rate and review time, "
            "and flags rubber-stamping — so human oversight stays meaningful.",
        ),
    ]

    implemented = sum(1 for c in controls if c["status"] == "implemented")
    return {
        "organization_id": principal.org_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "summary": {
            "controls_total": len(controls),
            "implemented": implemented,
            "partial": sum(1 for c in controls if c["status"] == "partial"),
            "not_configured": sum(1 for c in controls if c["status"] == "not_configured"),
        },
        "frameworks_covered": [
            "OWASP AI Exchange", "MITRE ATLAS", "ISO/IEC 42001", "ISO/IEC 27002",
            "EU AI Act", "SOC 2",
        ],
        "controls": controls,
    }
