"""Static catalog endpoints — scope domains and policy condition templates.

These endpoints return pre-built, read-only reference data that teams can
use as a starting point when configuring roles and policies. No database
access required — data is embedded in this module.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import Principal, get_principal

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ── Scope catalog ─────────────────────────────────────────────────────────────

SCOPE_DOMAINS = [
    {
        "domain": "finance",
        "label": "Finance & Banking",
        "description": "Payment processing, account management, and financial transactions",
        "scopes": [
            {"scope": "payment.initiate",     "description": "Initiate payment transactions",             "risk": "high"},
            {"scope": "payment.read",          "description": "Read payment history and receipts",         "risk": "low"},
            {"scope": "account.read",          "description": "View account balances and details",         "risk": "low"},
            {"scope": "account.update",        "description": "Modify account settings",                  "risk": "medium"},
            {"scope": "transaction.read",      "description": "View transaction records",                  "risk": "low"},
            {"scope": "transaction.reverse",   "description": "Reverse or refund a transaction",           "risk": "high"},
            {"scope": "fraud.flag",            "description": "Flag a transaction as potential fraud",     "risk": "medium"},
            {"scope": "report.generate",       "description": "Generate financial reports",               "risk": "low"},
            {"scope": "wire.initiate",         "description": "Initiate wire / ACH transfers",            "risk": "critical"},
            {"scope": "card.issue",            "description": "Issue or block a payment card",            "risk": "high"},
        ],
    },
    {
        "domain": "healthcare",
        "label": "Healthcare & Clinical",
        "description": "Patient records, prescriptions, appointments, and clinical data",
        "scopes": [
            {"scope": "patient.read",          "description": "View patient demographic data",             "risk": "medium"},
            {"scope": "patient.update",        "description": "Update patient records",                   "risk": "high"},
            {"scope": "records.read",          "description": "Read clinical / medical records",           "risk": "high"},
            {"scope": "records.write",         "description": "Create or amend clinical records",         "risk": "critical"},
            {"scope": "prescription.read",     "description": "View prescription history",                "risk": "medium"},
            {"scope": "prescription.write",    "description": "Issue or modify a prescription",           "risk": "critical"},
            {"scope": "appointment.read",      "description": "View scheduled appointments",              "risk": "low"},
            {"scope": "appointment.schedule",  "description": "Book or reschedule appointments",          "risk": "medium"},
            {"scope": "lab.read",              "description": "View lab results",                         "risk": "high"},
            {"scope": "billing.read",          "description": "View patient billing information",         "risk": "medium"},
        ],
    },
    {
        "domain": "ecommerce",
        "label": "E-commerce & Retail",
        "description": "Orders, products, inventory, and customer management",
        "scopes": [
            {"scope": "order.read",            "description": "View customer orders",                     "risk": "low"},
            {"scope": "order.update",          "description": "Update order status or details",           "risk": "medium"},
            {"scope": "order.cancel",          "description": "Cancel an order",                         "risk": "high"},
            {"scope": "order.refund",          "description": "Process order refund",                    "risk": "high"},
            {"scope": "product.read",          "description": "View product catalogue",                  "risk": "low"},
            {"scope": "product.update",        "description": "Update product details and pricing",      "risk": "medium"},
            {"scope": "inventory.read",        "description": "Read inventory levels",                   "risk": "low"},
            {"scope": "inventory.update",      "description": "Adjust stock quantities",                 "risk": "medium"},
            {"scope": "customer.read",         "description": "View customer profiles",                  "risk": "low"},
            {"scope": "cart.read",             "description": "View cart contents",                      "risk": "low"},
        ],
    },
    {
        "domain": "devops",
        "label": "DevOps & Engineering",
        "description": "Deployments, infrastructure, pipelines, and secret management",
        "scopes": [
            {"scope": "deploy.production",     "description": "Deploy to production environment",        "risk": "critical"},
            {"scope": "deploy.staging",        "description": "Deploy to staging environment",           "risk": "medium"},
            {"scope": "infra.read",            "description": "Read infrastructure configuration",       "risk": "low"},
            {"scope": "infra.update",          "description": "Modify infrastructure resources",         "risk": "high"},
            {"scope": "secret.read",           "description": "Read secrets or credentials",             "risk": "critical"},
            {"scope": "secret.rotate",         "description": "Rotate or update secrets",               "risk": "high"},
            {"scope": "pipeline.trigger",      "description": "Trigger a CI/CD pipeline",               "risk": "medium"},
            {"scope": "pipeline.read",         "description": "View pipeline runs and logs",             "risk": "low"},
            {"scope": "code.read",             "description": "Read source code repositories",           "risk": "medium"},
            {"scope": "code.write",            "description": "Push or merge code changes",             "risk": "high"},
        ],
    },
    {
        "domain": "crm",
        "label": "CRM & Sales",
        "description": "Contacts, deals, leads, and account management",
        "scopes": [
            {"scope": "crm.contact.read",      "description": "View contact records",                   "risk": "low"},
            {"scope": "crm.contact.write",     "description": "Create or update contacts",              "risk": "medium"},
            {"scope": "crm.contact.delete",    "description": "Delete contacts",                        "risk": "high"},
            {"scope": "crm.deal.read",         "description": "View deal pipeline",                     "risk": "low"},
            {"scope": "crm.deal.write",        "description": "Create or update deals",                 "risk": "medium"},
            {"scope": "crm.lead.read",         "description": "View leads",                             "risk": "low"},
            {"scope": "crm.lead.qualify",      "description": "Qualify or disqualify leads",            "risk": "medium"},
            {"scope": "crm.account.read",      "description": "View account information",               "risk": "low"},
            {"scope": "crm.email.send",        "description": "Send emails on behalf of sales reps",    "risk": "high"},
            {"scope": "crm.forecast.read",     "description": "View revenue forecasts",                 "risk": "low"},
        ],
    },
    {
        "domain": "data",
        "label": "Data & Analytics",
        "description": "Data access, exports, pipelines, and reporting",
        "scopes": [
            {"scope": "data.read",             "description": "Read datasets and tables",               "risk": "medium"},
            {"scope": "data.write",            "description": "Write or append to datasets",            "risk": "high"},
            {"scope": "data.export",           "description": "Export data to files or external systems","risk": "high"},
            {"scope": "data.delete",           "description": "Delete dataset rows or tables",          "risk": "critical"},
            {"scope": "analytics.read",        "description": "View dashboards and reports",            "risk": "low"},
            {"scope": "analytics.write",       "description": "Create or update reports",               "risk": "medium"},
            {"scope": "pipeline.read",         "description": "View data pipeline runs",                "risk": "low"},
            {"scope": "pipeline.trigger",      "description": "Trigger data pipeline runs",             "risk": "medium"},
            {"scope": "schema.read",           "description": "View database schemas",                  "risk": "low"},
            {"scope": "pii.access",            "description": "Access personally identifiable data",    "risk": "critical"},
        ],
    },
    {
        "domain": "hr",
        "label": "HR & Workforce",
        "description": "Employee records, payroll, leave management, and onboarding",
        "scopes": [
            {"scope": "hr.employee.read",      "description": "View employee profiles",                 "risk": "medium"},
            {"scope": "hr.employee.update",    "description": "Update employee information",            "risk": "high"},
            {"scope": "hr.payroll.read",       "description": "View payroll records",                   "risk": "high"},
            {"scope": "hr.payroll.run",        "description": "Execute payroll run",                   "risk": "critical"},
            {"scope": "hr.leave.read",         "description": "View leave balances",                    "risk": "low"},
            {"scope": "hr.leave.approve",      "description": "Approve or reject leave requests",       "risk": "medium"},
            {"scope": "hr.onboard.create",     "description": "Create onboarding workflows",            "risk": "medium"},
            {"scope": "hr.offboard.execute",   "description": "Execute employee offboarding",           "risk": "high"},
            {"scope": "hr.performance.read",   "description": "View performance reviews",               "risk": "medium"},
            {"scope": "hr.org.read",           "description": "View organizational hierarchy",          "risk": "low"},
        ],
    },
    {
        "domain": "security",
        "label": "IT Security & IAM",
        "description": "Identity management, access controls, and security operations",
        "scopes": [
            {"scope": "iam.user.read",         "description": "View user identities",                   "risk": "low"},
            {"scope": "iam.user.provision",    "description": "Create or modify user accounts",         "risk": "high"},
            {"scope": "iam.role.assign",       "description": "Assign roles to users",                  "risk": "critical"},
            {"scope": "iam.token.revoke",      "description": "Revoke access tokens or API keys",       "risk": "high"},
            {"scope": "security.alert.read",   "description": "View security alerts",                   "risk": "low"},
            {"scope": "security.incident.create", "description": "Create security incidents",           "risk": "medium"},
            {"scope": "network.firewall.read", "description": "View firewall rules",                    "risk": "medium"},
            {"scope": "network.firewall.update","description": "Modify firewall rules",                 "risk": "critical"},
            {"scope": "audit.read",            "description": "Read audit logs",                        "risk": "low"},
            {"scope": "mfa.bypass",            "description": "Bypass multi-factor authentication",     "risk": "critical"},
        ],
    },
]


# ── Policy condition templates ────────────────────────────────────────────────

POLICY_TEMPLATES = [
    {
        "id": "business-hours",
        "label": "Business hours only",
        "description": "Allow actions only during 9AM–6PM",
        "suggested_effect": "allow",
        "condition": {
            "op": "time_between",
            "args": ["ctx.context.time", "09:00", "18:00"],
        },
    },
    {
        "id": "country-allowlist",
        "label": "Region / country allowlist",
        "description": "Restrict to specific countries (US and CA shown as example)",
        "suggested_effect": "allow",
        "condition": {
            "op": "in",
            "args": ["ctx.context.ip_country", ["US", "CA"]],
        },
    },
    {
        "id": "business-hours-and-region",
        "label": "Business hours + region",
        "description": "Allow only within business hours AND from an approved country",
        "suggested_effect": "allow",
        "condition": {
            "op": "and",
            "args": [
                {"op": "time_between", "args": ["ctx.context.time", "09:00", "18:00"]},
                {"op": "in", "args": ["ctx.context.ip_country", ["US", "CA", "GB"]]},
            ],
        },
    },
    {
        "id": "low-risk-only",
        "label": "Low-risk resources only",
        "description": "Allow only when the resource is classified as public or low-risk",
        "suggested_effect": "allow",
        "condition": {
            "op": "in",
            "args": ["ctx.resource.attrs.classification", ["public", "low"]],
        },
    },
    {
        "id": "deny-sensitive-data",
        "label": "Block sensitive / PII data",
        "description": "Deny access when the resource contains sensitive or PII data",
        "suggested_effect": "deny",
        "condition": {
            "op": "in",
            "args": ["ctx.resource.attrs.classification", ["sensitive", "pii", "restricted", "confidential"]],
        },
    },
    {
        "id": "require-scope",
        "label": "Require a specific granted scope",
        "description": "Allow only if the subject already holds a required scope (e.g. data.read)",
        "suggested_effect": "allow",
        "condition": {
            "op": "has_scope",
            "args": ["ctx.subject.attrs.scopes", "data.read"],
        },
    },
    {
        "id": "require-approval-high-risk",
        "label": "Escalate high-risk resources",
        "description": "Route to human approval when resource risk_class is high or critical",
        "suggested_effect": "require_approval",
        "condition": {
            "op": "in",
            "args": ["ctx.resource.attrs.risk_class", ["high", "critical"]],
        },
    },
    {
        "id": "require-approval-production",
        "label": "Escalate production environment actions",
        "description": "Require human approval before any action on production resources",
        "suggested_effect": "require_approval",
        "condition": {
            "op": "eq",
            "args": ["ctx.resource.attrs.environment", "production"],
        },
    },
    {
        "id": "deny-outside-hours",
        "label": "Block after-hours access",
        "description": "Deny all requests outside of 9AM–6PM",
        "suggested_effect": "deny",
        "condition": {
            "op": "not",
            "args": [{"op": "time_between", "args": ["ctx.context.time", "09:00", "18:00"]}],
        },
    },
    {
        "id": "match-all",
        "label": "Match all requests (no condition)",
        "description": "Apply to every request unconditionally — useful as a catch-all at low priority",
        "suggested_effect": "allow",
        "condition": {},
    },
]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/scope-domains")
async def list_scope_domains(_: Principal = Depends(get_principal)):
    """Return all pre-built scope domains grouped by industry."""
    return SCOPE_DOMAINS


@router.get("/scope-domains/{domain}")
async def get_scope_domain(domain: str, _: Principal = Depends(get_principal)):
    """Return a single scope domain by its identifier."""
    from fastapi import HTTPException
    match = next((d for d in SCOPE_DOMAINS if d["domain"] == domain), None)
    if not match:
        raise HTTPException(404, f"Scope domain '{domain}' not found")
    return match


@router.get("/policy-templates")
async def list_policy_templates(_: Principal = Depends(get_principal)):
    """Return all pre-built condition templates for bootstrapping new policies."""
    return POLICY_TEMPLATES
