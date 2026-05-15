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


# ── Pre-built tool templates ──────────────────────────────────────────────────

TOOL_TEMPLATES = [
    # ── Finance & Banking ─────────────────────────────────────────────────────
    {
        "id": "finance-refund-issue",
        "domain": "finance",
        "domain_label": "Finance & Banking",
        "namespace": "payments",
        "name": "refund.issue",
        "display_name": "Issue Refund",
        "description": "Process a customer refund for a given transaction",
        "risk_class": "high",
        "scopes": ["payment.initiate", "transaction.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string", "description": "ID of the original transaction"},
                "amount": {"type": "number", "description": "Refund amount in cents"},
                "reason": {"type": "string", "enum": ["duplicate", "fraudulent", "customer_request"], "description": "Reason for the refund"},
            },
            "required": ["transaction_id", "amount"],
        },
    },
    {
        "id": "finance-transaction-list",
        "domain": "finance",
        "domain_label": "Finance & Banking",
        "namespace": "payments",
        "name": "transaction.list",
        "display_name": "List Transactions",
        "description": "Retrieve a paginated list of transactions for an account",
        "risk_class": "low",
        "scopes": ["transaction.read", "account.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account identifier"},
                "from_date": {"type": "string", "format": "date", "description": "Start date (YYYY-MM-DD)"},
                "to_date": {"type": "string", "format": "date", "description": "End date (YYYY-MM-DD)"},
                "limit": {"type": "integer", "default": 50, "description": "Max results to return"},
            },
            "required": ["account_id"],
        },
    },
    {
        "id": "finance-wire-transfer",
        "domain": "finance",
        "domain_label": "Finance & Banking",
        "namespace": "payments",
        "name": "wire.transfer",
        "display_name": "Initiate Wire Transfer",
        "description": "Initiate a domestic or international wire / ACH transfer",
        "risk_class": "critical",
        "scopes": ["wire.initiate"],
        "input_schema": {
            "type": "object",
            "properties": {
                "from_account": {"type": "string", "description": "Source account ID"},
                "to_account": {"type": "string", "description": "Destination account or routing info"},
                "amount": {"type": "number", "description": "Transfer amount in cents"},
                "currency": {"type": "string", "default": "USD"},
                "memo": {"type": "string", "description": "Transfer memo / reference"},
            },
            "required": ["from_account", "to_account", "amount"],
        },
    },
    {
        "id": "finance-fraud-flag",
        "domain": "finance",
        "domain_label": "Finance & Banking",
        "namespace": "fraud",
        "name": "transaction.flag",
        "display_name": "Flag Suspicious Transaction",
        "description": "Mark a transaction as potentially fraudulent for review",
        "risk_class": "medium",
        "scopes": ["fraud.flag", "transaction.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string", "description": "Transaction to flag"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "Fraud confidence score 0–1"},
                "reason": {"type": "string", "description": "Short description of suspicious signal"},
            },
            "required": ["transaction_id", "confidence"],
        },
    },
    {
        "id": "finance-report-generate",
        "domain": "finance",
        "domain_label": "Finance & Banking",
        "namespace": "reports",
        "name": "financial.generate",
        "display_name": "Generate Financial Report",
        "description": "Generate a financial summary report for a given period",
        "risk_class": "low",
        "scopes": ["report.generate", "account.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "enum": ["profit_loss", "balance_sheet", "cash_flow"], "description": "Type of report"},
                "period_start": {"type": "string", "format": "date"},
                "period_end": {"type": "string", "format": "date"},
                "format": {"type": "string", "enum": ["pdf", "csv", "json"], "default": "pdf"},
            },
            "required": ["report_type", "period_start", "period_end"],
        },
    },
    # ── Healthcare & Clinical ─────────────────────────────────────────────────
    {
        "id": "healthcare-patient-lookup",
        "domain": "healthcare",
        "domain_label": "Healthcare & Clinical",
        "namespace": "ehr",
        "name": "patient.lookup",
        "display_name": "Look Up Patient",
        "description": "Retrieve demographic and summary data for a patient",
        "risk_class": "medium",
        "scopes": ["patient.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "Patient MRN or system ID"},
                "include_allergies": {"type": "boolean", "default": False},
            },
            "required": ["patient_id"],
        },
    },
    {
        "id": "healthcare-appointment-book",
        "domain": "healthcare",
        "domain_label": "Healthcare & Clinical",
        "namespace": "ehr",
        "name": "appointment.book",
        "display_name": "Book Appointment",
        "description": "Schedule or reschedule a clinical appointment",
        "risk_class": "medium",
        "scopes": ["appointment.schedule", "patient.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "provider_id": {"type": "string", "description": "Clinician or department ID"},
                "slot_datetime": {"type": "string", "format": "date-time"},
                "visit_type": {"type": "string", "enum": ["in_person", "telehealth"], "default": "in_person"},
            },
            "required": ["patient_id", "provider_id", "slot_datetime"],
        },
    },
    {
        "id": "healthcare-prescription-create",
        "domain": "healthcare",
        "domain_label": "Healthcare & Clinical",
        "namespace": "ehr",
        "name": "prescription.create",
        "display_name": "Create Prescription",
        "description": "Issue a new medication prescription for a patient",
        "risk_class": "critical",
        "scopes": ["prescription.write", "patient.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "medication_code": {"type": "string", "description": "RxNorm or NDC code"},
                "dosage": {"type": "string", "description": "Dosage and frequency e.g. 500mg twice daily"},
                "duration_days": {"type": "integer"},
                "prescriber_id": {"type": "string"},
            },
            "required": ["patient_id", "medication_code", "dosage", "prescriber_id"],
        },
    },
    {
        "id": "healthcare-lab-read",
        "domain": "healthcare",
        "domain_label": "Healthcare & Clinical",
        "namespace": "ehr",
        "name": "lab.result.read",
        "display_name": "Read Lab Results",
        "description": "Retrieve laboratory test results for a patient",
        "risk_class": "high",
        "scopes": ["lab.read", "patient.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "test_type": {"type": "string", "description": "LOINC code or test category"},
                "from_date": {"type": "string", "format": "date"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "id": "healthcare-records-summarize",
        "domain": "healthcare",
        "domain_label": "Healthcare & Clinical",
        "namespace": "ehr",
        "name": "records.summarize",
        "display_name": "Summarize Clinical Records",
        "description": "Generate a summary of a patient's clinical history",
        "risk_class": "high",
        "scopes": ["records.read", "patient.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "sections": {"type": "array", "items": {"type": "string"}, "description": "Sections to include e.g. diagnoses, medications"},
            },
            "required": ["patient_id"],
        },
    },
    # ── E-commerce & Retail ───────────────────────────────────────────────────
    {
        "id": "ecommerce-order-cancel",
        "domain": "ecommerce",
        "domain_label": "E-commerce & Retail",
        "namespace": "orders",
        "name": "order.cancel",
        "display_name": "Cancel Order",
        "description": "Cancel an open order and trigger any refund logic",
        "risk_class": "high",
        "scopes": ["order.cancel", "order.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string", "enum": ["customer_request", "fraud", "inventory", "other"]},
                "notify_customer": {"type": "boolean", "default": True},
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "id": "ecommerce-order-refund",
        "domain": "ecommerce",
        "domain_label": "E-commerce & Retail",
        "namespace": "orders",
        "name": "order.refund",
        "display_name": "Issue Order Refund",
        "description": "Issue a full or partial refund for a completed order",
        "risk_class": "high",
        "scopes": ["order.refund", "order.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "refund_amount": {"type": "number", "description": "Amount in cents; omit for full refund"},
                "line_item_ids": {"type": "array", "items": {"type": "string"}, "description": "Specific items to refund"},
            },
            "required": ["order_id"],
        },
    },
    {
        "id": "ecommerce-stock-adjust",
        "domain": "ecommerce",
        "domain_label": "E-commerce & Retail",
        "namespace": "inventory",
        "name": "stock.adjust",
        "display_name": "Adjust Stock Level",
        "description": "Update inventory quantity for a product SKU",
        "risk_class": "medium",
        "scopes": ["inventory.update", "inventory.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "warehouse_id": {"type": "string"},
                "delta": {"type": "integer", "description": "Quantity change — positive to add, negative to remove"},
                "note": {"type": "string"},
            },
            "required": ["sku", "delta"],
        },
    },
    {
        "id": "ecommerce-price-update",
        "domain": "ecommerce",
        "domain_label": "E-commerce & Retail",
        "namespace": "products",
        "name": "price.update",
        "display_name": "Update Product Price",
        "description": "Update the selling price for a product",
        "risk_class": "medium",
        "scopes": ["product.update"],
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "price": {"type": "number", "description": "New price in cents"},
                "currency": {"type": "string", "default": "USD"},
                "effective_from": {"type": "string", "format": "date-time"},
            },
            "required": ["product_id", "price"],
        },
    },
    {
        "id": "ecommerce-customer-lookup",
        "domain": "ecommerce",
        "domain_label": "E-commerce & Retail",
        "namespace": "customers",
        "name": "profile.lookup",
        "display_name": "Look Up Customer",
        "description": "Retrieve a customer profile by ID or email",
        "risk_class": "low",
        "scopes": ["customer.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "email": {"type": "string", "format": "email"},
            },
        },
    },
    # ── DevOps & Engineering ──────────────────────────────────────────────────
    {
        "id": "devops-production-deploy",
        "domain": "devops",
        "domain_label": "DevOps & Engineering",
        "namespace": "deploy",
        "name": "production.release",
        "display_name": "Deploy to Production",
        "description": "Trigger a production deployment for a service",
        "risk_class": "critical",
        "scopes": ["deploy.production"],
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service or repository name"},
                "image_tag": {"type": "string", "description": "Docker image tag or git ref"},
                "rollback_on_failure": {"type": "boolean", "default": True},
                "notify_channel": {"type": "string", "description": "Slack channel for deploy notification"},
            },
            "required": ["service", "image_tag"],
        },
    },
    {
        "id": "devops-staging-deploy",
        "domain": "devops",
        "domain_label": "DevOps & Engineering",
        "namespace": "deploy",
        "name": "staging.release",
        "display_name": "Deploy to Staging",
        "description": "Trigger a staging environment deployment",
        "risk_class": "medium",
        "scopes": ["deploy.staging"],
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "image_tag": {"type": "string"},
                "environment": {"type": "string", "default": "staging"},
            },
            "required": ["service", "image_tag"],
        },
    },
    {
        "id": "devops-secret-rotate",
        "domain": "devops",
        "domain_label": "DevOps & Engineering",
        "namespace": "secrets",
        "name": "secret.rotate",
        "display_name": "Rotate Secret",
        "description": "Rotate a credential or API key in the secrets store",
        "risk_class": "high",
        "scopes": ["secret.rotate", "secret.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "secret_name": {"type": "string", "description": "Secret identifier in the vault"},
                "notify_dependent_services": {"type": "boolean", "default": True},
            },
            "required": ["secret_name"],
        },
    },
    {
        "id": "devops-pipeline-trigger",
        "domain": "devops",
        "domain_label": "DevOps & Engineering",
        "namespace": "pipeline",
        "name": "build.trigger",
        "display_name": "Trigger CI Pipeline",
        "description": "Kick off a CI/CD pipeline run for a repository",
        "risk_class": "medium",
        "scopes": ["pipeline.trigger", "pipeline.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Repository slug e.g. org/repo"},
                "branch": {"type": "string", "default": "main"},
                "pipeline_id": {"type": "string", "description": "Pipeline or workflow ID"},
                "variables": {"type": "object", "description": "Optional env overrides"},
            },
            "required": ["repo"],
        },
    },
    {
        "id": "devops-infra-update",
        "domain": "devops",
        "domain_label": "DevOps & Engineering",
        "namespace": "infra",
        "name": "config.update",
        "display_name": "Update Infrastructure Config",
        "description": "Apply an infrastructure configuration change (e.g. Terraform variable)",
        "risk_class": "high",
        "scopes": ["infra.update", "infra.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string", "description": "Resource path e.g. aws_rds_instance.main"},
                "changes": {"type": "object", "description": "Key-value pairs to update"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["resource", "changes"],
        },
    },
    # ── CRM & Sales ───────────────────────────────────────────────────────────
    {
        "id": "crm-contact-create",
        "domain": "crm",
        "domain_label": "CRM & Sales",
        "namespace": "crm",
        "name": "contact.create",
        "display_name": "Create Contact",
        "description": "Create a new CRM contact record",
        "risk_class": "medium",
        "scopes": ["crm.contact.write"],
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "source": {"type": "string", "description": "Lead source e.g. website, referral"},
            },
            "required": ["first_name", "last_name", "email"],
        },
    },
    {
        "id": "crm-deal-update",
        "domain": "crm",
        "domain_label": "CRM & Sales",
        "namespace": "crm",
        "name": "deal.update",
        "display_name": "Update Deal",
        "description": "Update deal stage, value, or owner in the sales pipeline",
        "risk_class": "medium",
        "scopes": ["crm.deal.write", "crm.deal.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string"},
                "stage": {"type": "string", "description": "Pipeline stage name"},
                "amount": {"type": "number", "description": "Deal value in currency units"},
                "close_date": {"type": "string", "format": "date"},
                "owner_id": {"type": "string"},
            },
            "required": ["deal_id"],
        },
    },
    {
        "id": "crm-lead-qualify",
        "domain": "crm",
        "domain_label": "CRM & Sales",
        "namespace": "crm",
        "name": "lead.qualify",
        "display_name": "Qualify Lead",
        "description": "Mark a lead as qualified or disqualified with a reason",
        "risk_class": "medium",
        "scopes": ["crm.lead.qualify", "crm.lead.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "qualified": {"type": "boolean"},
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "disqualification_reason": {"type": "string"},
            },
            "required": ["lead_id", "qualified"],
        },
    },
    {
        "id": "crm-email-send",
        "domain": "crm",
        "domain_label": "CRM & Sales",
        "namespace": "crm",
        "name": "email.send",
        "display_name": "Send Sales Email",
        "description": "Send a templated or custom email to a CRM contact",
        "risk_class": "high",
        "scopes": ["crm.email.send", "crm.contact.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string"},
                "template_id": {"type": "string", "description": "Email template ID; omit to send custom"},
                "subject": {"type": "string"},
                "body_html": {"type": "string"},
                "from_rep_id": {"type": "string", "description": "Sales rep to send as"},
            },
            "required": ["contact_id", "subject"],
        },
    },
    {
        "id": "crm-forecast-read",
        "domain": "crm",
        "domain_label": "CRM & Sales",
        "namespace": "crm",
        "name": "forecast.read",
        "display_name": "Read Revenue Forecast",
        "description": "Retrieve the revenue forecast for a given quarter",
        "risk_class": "low",
        "scopes": ["crm.forecast.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "quarter": {"type": "string", "description": "e.g. 2024-Q3"},
                "team_id": {"type": "string"},
            },
            "required": ["quarter"],
        },
    },
    # ── Data & Analytics ──────────────────────────────────────────────────────
    {
        "id": "data-dataset-query",
        "domain": "data",
        "domain_label": "Data & Analytics",
        "namespace": "data",
        "name": "dataset.query",
        "display_name": "Query Dataset",
        "description": "Execute a read-only query against a named dataset",
        "risk_class": "medium",
        "scopes": ["data.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "description": "Dataset or table name"},
                "sql": {"type": "string", "description": "SELECT query — must be read-only"},
                "limit": {"type": "integer", "default": 1000},
            },
            "required": ["dataset", "sql"],
        },
    },
    {
        "id": "data-report-export",
        "domain": "data",
        "domain_label": "Data & Analytics",
        "namespace": "data",
        "name": "report.export",
        "display_name": "Export Report",
        "description": "Export a dashboard report to CSV or JSON",
        "risk_class": "high",
        "scopes": ["data.export", "analytics.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string"},
                "format": {"type": "string", "enum": ["csv", "json", "parquet"], "default": "csv"},
                "date_range": {
                    "type": "object",
                    "properties": {
                        "from": {"type": "string", "format": "date"},
                        "to": {"type": "string", "format": "date"},
                    },
                },
            },
            "required": ["report_id"],
        },
    },
    {
        "id": "data-pipeline-run",
        "domain": "data",
        "domain_label": "Data & Analytics",
        "namespace": "data",
        "name": "pipeline.run",
        "display_name": "Run Data Pipeline",
        "description": "Trigger an ETL/ELT data pipeline run",
        "risk_class": "medium",
        "scopes": ["pipeline.trigger"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "string"},
                "backfill_from": {"type": "string", "format": "date", "description": "Optional backfill start date"},
                "full_refresh": {"type": "boolean", "default": False},
            },
            "required": ["pipeline_id"],
        },
    },
    {
        "id": "data-pii-lookup",
        "domain": "data",
        "domain_label": "Data & Analytics",
        "namespace": "data",
        "name": "pii.lookup",
        "display_name": "Access PII Data",
        "description": "Retrieve personally identifiable information for a subject",
        "risk_class": "critical",
        "scopes": ["pii.access", "data.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "subject_id": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}, "description": "Specific PII fields to return"},
                "purpose": {"type": "string", "description": "Legal basis / business purpose for the access"},
            },
            "required": ["subject_id", "purpose"],
        },
    },
    {
        "id": "data-dashboard-create",
        "domain": "data",
        "domain_label": "Data & Analytics",
        "namespace": "analytics",
        "name": "dashboard.create",
        "display_name": "Create Dashboard",
        "description": "Create a new analytics dashboard from a dataset",
        "risk_class": "medium",
        "scopes": ["analytics.write"],
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "dataset": {"type": "string"},
                "chart_types": {"type": "array", "items": {"type": "string"}, "description": "e.g. bar, line, pie"},
                "owner_id": {"type": "string"},
            },
            "required": ["name", "dataset"],
        },
    },
    # ── HR & Workforce ────────────────────────────────────────────────────────
    {
        "id": "hr-employee-lookup",
        "domain": "hr",
        "domain_label": "HR & Workforce",
        "namespace": "hr",
        "name": "employee.lookup",
        "display_name": "Look Up Employee",
        "description": "Retrieve an employee profile by ID or name",
        "risk_class": "medium",
        "scopes": ["hr.employee.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string"},
                "include_org_chart": {"type": "boolean", "default": False},
            },
            "required": ["employee_id"],
        },
    },
    {
        "id": "hr-leave-approve",
        "domain": "hr",
        "domain_label": "HR & Workforce",
        "namespace": "hr",
        "name": "leave.approve",
        "display_name": "Approve Leave Request",
        "description": "Approve or reject an employee leave request",
        "risk_class": "medium",
        "scopes": ["hr.leave.approve", "hr.leave.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
                "notes": {"type": "string"},
            },
            "required": ["request_id", "decision"],
        },
    },
    {
        "id": "hr-payroll-run",
        "domain": "hr",
        "domain_label": "HR & Workforce",
        "namespace": "hr",
        "name": "payroll.run",
        "display_name": "Execute Payroll Run",
        "description": "Kick off a payroll processing run for a pay period",
        "risk_class": "critical",
        "scopes": ["hr.payroll.run", "hr.payroll.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pay_period": {"type": "string", "description": "e.g. 2024-06-01/2024-06-15"},
                "payroll_group": {"type": "string", "description": "e.g. us_fulltime, contractors"},
                "dry_run": {"type": "boolean", "default": True, "description": "Simulate without disbursing"},
            },
            "required": ["pay_period"],
        },
    },
    {
        "id": "hr-onboard-create",
        "domain": "hr",
        "domain_label": "HR & Workforce",
        "namespace": "hr",
        "name": "onboard.create",
        "display_name": "Create Onboarding Workflow",
        "description": "Provision accounts and kick off an onboarding checklist for a new hire",
        "risk_class": "medium",
        "scopes": ["hr.onboard.create", "hr.employee.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string"},
                "start_date": {"type": "string", "format": "date"},
                "department": {"type": "string"},
                "manager_id": {"type": "string"},
                "systems": {"type": "array", "items": {"type": "string"}, "description": "Systems to provision e.g. github, slack, jira"},
            },
            "required": ["employee_id", "start_date"],
        },
    },
    {
        "id": "hr-offboard-execute",
        "domain": "hr",
        "domain_label": "HR & Workforce",
        "namespace": "hr",
        "name": "offboard.execute",
        "display_name": "Execute Offboarding",
        "description": "Revoke access and execute offboarding steps for a departing employee",
        "risk_class": "high",
        "scopes": ["hr.offboard.execute", "hr.employee.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string"},
                "last_day": {"type": "string", "format": "date"},
                "revoke_access_immediately": {"type": "boolean", "default": False},
                "data_retention_days": {"type": "integer", "default": 30},
            },
            "required": ["employee_id", "last_day"],
        },
    },
    # ── IT Security & IAM ─────────────────────────────────────────────────────
    {
        "id": "security-user-provision",
        "domain": "security",
        "domain_label": "IT Security & IAM",
        "namespace": "iam",
        "name": "user.provision",
        "display_name": "Provision User",
        "description": "Create a new user identity in the IAM system",
        "risk_class": "high",
        "scopes": ["iam.user.provision"],
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "groups": {"type": "array", "items": {"type": "string"}},
                "mfa_required": {"type": "boolean", "default": True},
            },
            "required": ["username", "email"],
        },
    },
    {
        "id": "security-role-assign",
        "domain": "security",
        "domain_label": "IT Security & IAM",
        "namespace": "iam",
        "name": "role.assign",
        "display_name": "Assign IAM Role",
        "description": "Assign an IAM role to a user or service account",
        "risk_class": "critical",
        "scopes": ["iam.role.assign", "iam.user.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "principal_id": {"type": "string", "description": "User or service account ID"},
                "role": {"type": "string", "description": "Role ARN or name"},
                "expires_at": {"type": "string", "format": "date-time", "description": "Optional expiry for temporary grants"},
                "justification": {"type": "string"},
            },
            "required": ["principal_id", "role"],
        },
    },
    {
        "id": "security-token-revoke",
        "domain": "security",
        "domain_label": "IT Security & IAM",
        "namespace": "iam",
        "name": "token.revoke",
        "display_name": "Revoke Access Token",
        "description": "Immediately revoke an API key or access token",
        "risk_class": "high",
        "scopes": ["iam.token.revoke"],
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {"type": "string", "description": "Token identifier or prefix"},
                "reason": {"type": "string", "description": "Reason for revocation"},
                "notify_owner": {"type": "boolean", "default": True},
            },
            "required": ["token_id", "reason"],
        },
    },
    {
        "id": "security-incident-create",
        "domain": "security",
        "domain_label": "IT Security & IAM",
        "namespace": "security",
        "name": "incident.create",
        "display_name": "Create Security Incident",
        "description": "Open a new security incident from an alert or observation",
        "risk_class": "medium",
        "scopes": ["security.incident.create", "security.alert.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "description": {"type": "string"},
                "alert_ids": {"type": "array", "items": {"type": "string"}, "description": "Linked alert IDs"},
                "assignee_id": {"type": "string"},
            },
            "required": ["title", "severity"],
        },
    },
    {
        "id": "security-firewall-update",
        "domain": "security",
        "domain_label": "IT Security & IAM",
        "namespace": "network",
        "name": "firewall.update",
        "display_name": "Update Firewall Rule",
        "description": "Add, modify, or remove a network firewall rule",
        "risk_class": "critical",
        "scopes": ["network.firewall.update", "network.firewall.read"],
        "input_schema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string", "description": "Existing rule ID; omit to create new"},
                "action": {"type": "string", "enum": ["allow", "deny", "drop"]},
                "protocol": {"type": "string", "enum": ["tcp", "udp", "icmp", "any"]},
                "source_cidr": {"type": "string"},
                "dest_cidr": {"type": "string"},
                "port": {"type": "integer"},
            },
            "required": ["action", "protocol"],
        },
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


@router.get("/tool-templates")
async def list_tool_templates(_: Principal = Depends(get_principal)):
    """Return all pre-built tool templates grouped by domain."""
    from collections import defaultdict
    by_domain: dict = defaultdict(lambda: {"domain": "", "label": "", "tools": []})
    for t in TOOL_TEMPLATES:
        d = t["domain"]
        by_domain[d]["domain"] = d
        by_domain[d]["label"] = t["domain_label"]
        by_domain[d]["tools"].append(t)
    # Return in same order as SCOPE_DOMAINS
    domain_order = [sd["domain"] for sd in SCOPE_DOMAINS]
    result = [by_domain[d] for d in domain_order if d in by_domain]
    return result


@router.get("/tool-templates/{domain}")
async def get_tool_templates_by_domain(domain: str, _: Principal = Depends(get_principal)):
    """Return pre-built tool templates for a specific domain."""
    from fastapi import HTTPException
    tools = [t for t in TOOL_TEMPLATES if t["domain"] == domain]
    if not tools:
        raise HTTPException(404, f"No tool templates found for domain '{domain}'")
    return tools
