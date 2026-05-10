"""Seed a demo org with users, roles, agents, tools, and sample policies.

Run: ``python -m app.scripts.seed``
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.db.session import SessionLocal
from app.models import (
    Agent, AgentAssignment, OrgMembership, Organization, Policy, PolicyBinding,
    Role, RolePermission, Subscription, Tool, ToolScope, User,
)


async def main() -> None:
    async with SessionLocal() as s:
        # --- Org
        org = await s.scalar(select(Organization).where(Organization.slug == "acme"))
        if org:
            print(f"acme already seeded (org_id={org.id})")
            return

        org = Organization(name="Acme Industries", slug="acme", plan="business", is_trialing=False)
        s.add(org); await s.flush()

        # --- Users
        admin = User(email="admin@demo.kynara.dev", display_name="Demo Admin",
                     password_hash=hash_password("kynara-demo"), mfa_enrolled=True)
        dev = User(email="dev@demo.kynara.dev", display_name="Demo Developer",
                   password_hash=hash_password("kynara-demo"))
        auditor = User(email="auditor@demo.kynara.dev", display_name="Demo Auditor",
                       password_hash=hash_password("kynara-demo"))
        s.add_all([admin, dev, auditor]); await s.flush()

        s.add_all([
            OrgMembership(organization_id=org.id, user_id=admin.id, seat_role="owner"),
            OrgMembership(organization_id=org.id, user_id=dev.id, seat_role="developer"),
            OrgMembership(organization_id=org.id, user_id=auditor.id, seat_role="auditor"),
        ])

        # --- Roles
        crm_role = Role(organization_id=org.id, slug="crm-reader",
                        display_name="CRM Reader",
                        description="Read-only access to CRM contacts and notes.")
        support_role = Role(organization_id=org.id, slug="support-agent",
                            display_name="Support Agent",
                            description="CRM read, ticket create/update, no account access.")
        s.add_all([crm_role, support_role]); await s.flush()

        s.add_all([
            RolePermission(role_id=crm_role.id, scope="crm.contacts.read"),
            RolePermission(role_id=crm_role.id, scope="crm.notes.read"),
            RolePermission(role_id=support_role.id, scope="crm.contacts.read"),
            RolePermission(role_id=support_role.id, scope="tickets.*"),
        ])

        # --- Tools
        t_crm_read = Tool(organization_id=org.id, namespace="crm", name="contacts.read",
                          description="Fetch a CRM contact", risk_class="low",
                          input_schema={"type": "object", "properties": {"id": {"type": "string"}}})
        t_email = Tool(organization_id=org.id, namespace="email", name="send",
                       description="Send a transactional email", risk_class="medium",
                       input_schema={"type": "object", "properties": {
                           "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}})
        t_refund = Tool(organization_id=org.id, namespace="payments", name="refund.issue",
                        description="Issue a full or partial refund", risk_class="critical",
                        input_schema={"type": "object", "properties": {
                            "payment_id": {"type": "string"}, "amount_cents": {"type": "integer"}}})
        s.add_all([t_crm_read, t_email, t_refund]); await s.flush()
        s.add_all([
            ToolScope(tool_id=t_crm_read.id, scope="crm.contacts.read"),
            ToolScope(tool_id=t_email.id, scope="email.send"),
            ToolScope(tool_id=t_refund.id, scope="payments.refund.issue"),
        ])

        # --- Agents
        crm_bot = Agent(organization_id=org.id, slug="crm-assistant",
                        display_name="CRM Assistant",
                        description="Pulls customer context for support reps",
                        mode="human_supervised", model="claude-sonnet-4-6",
                        daily_action_budget=5000)
        support_bot = Agent(organization_id=org.id, slug="support-triage",
                            display_name="Support Triage",
                            description="Categorizes and assigns incoming tickets",
                            mode="autonomous", model="claude-sonnet-4-6",
                            daily_action_budget=20000)
        s.add_all([crm_bot, support_bot]); await s.flush()

        s.add_all([
            AgentAssignment(organization_id=org.id, agent_id=crm_bot.id,
                            user_id=dev.id, role_id=crm_role.id),
            AgentAssignment(organization_id=org.id, agent_id=support_bot.id,
                            user_id=dev.id, role_id=support_role.id),
        ])

        # --- Policies
        p_deny_offhours = Policy(
            organization_id=org.id, slug="deny-offhours-refunds",
            display_name="Deny off-hours refunds",
            description="No refunds outside business hours without explicit approval.",
            effect="require_approval", priority=100,
            actions=["payments.refund.issue"],
            resource_types=["payment"],
            condition={"op": "not", "args": [
                {"op": "time_between", "args": ["ctx.context.time", "09:00", "18:00"]},
            ]},
        )
        p_deny_hirisk_autonomous = Policy(
            organization_id=org.id, slug="deny-high-risk-autonomous",
            display_name="Deny autonomous high-risk actions",
            description="Autonomous agents must not execute high-risk tools without supervision.",
            effect="deny", priority=50,
            actions=["payments.*", "db.write"],
            resource_types=[],
            condition={"op": "eq", "args": ["ctx.subject.attrs.mode", "autonomous"]},
        )
        p_allow_crm_reads_eu = Policy(
            organization_id=org.id, slug="allow-crm-reads-eu",
            display_name="Allow CRM reads only from EU egress",
            description="Data-residency control — CRM reads restricted to EU IP space.",
            effect="allow", priority=200,
            actions=["crm.contacts.read", "crm.notes.read"],
            resource_types=["crm.contact"],
            condition={"op": "in", "args": ["ctx.context.ip_country", ["DE", "FR", "IE", "NL"]]},
        )
        s.add_all([p_deny_offhours, p_deny_hirisk_autonomous, p_allow_crm_reads_eu])
        await s.flush()

        s.add_all([
            PolicyBinding(organization_id=org.id, policy_id=p_deny_offhours.id, subject_selector="*"),
            PolicyBinding(organization_id=org.id, policy_id=p_deny_hirisk_autonomous.id, subject_selector="*"),
            PolicyBinding(organization_id=org.id, policy_id=p_allow_crm_reads_eu.id,
                          subject_selector=f"agent:{crm_bot.id}"),
        ])

        # --- Subscription
        s.add(Subscription(
            organization_id=org.id, plan="business", status="active",
            seats_included=25, decisions_included=1_000_000, overage_cents_per_1k=50,
        ))

        await s.commit()
        print(f"Seeded demo org {org.id}")
        print("Login: admin@demo.kynara.dev / kynara-demo")


if __name__ == "__main__":
    asyncio.run(main())
