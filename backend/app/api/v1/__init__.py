from fastapi import APIRouter

from app.api.v1 import (
    admin, agents, api_keys, approvals, audit, auth, billing, catalog, contact,
    decisions, guardrails, health, invites, oauth, org, policies, roles,
    sso, sso_connections, tools, webhooks,
    # New feature routers
    activity_stream, agent_credentials, delegation, git_sync,
    policy_simulation, policy_templates,
)

v1 = APIRouter(prefix="/api/v1", redirect_slashes=False)
v1.include_router(health.router)
v1.include_router(auth.router)
v1.include_router(admin.router)
v1.include_router(invites.router)
v1.include_router(sso.router)
v1.include_router(sso_connections.router)
v1.include_router(org.router)
v1.include_router(agents.router)
v1.include_router(tools.router)
v1.include_router(catalog.router)
v1.include_router(roles.router)
v1.include_router(policies.router)
v1.include_router(decisions.router)
v1.include_router(approvals.router)
v1.include_router(audit.router)
v1.include_router(billing.router)
v1.include_router(contact.router)
v1.include_router(api_keys.router)
v1.include_router(guardrails.router)
v1.include_router(webhooks.router)
# Ne