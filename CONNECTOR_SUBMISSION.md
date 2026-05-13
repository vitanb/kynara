# Kynara — Claude Connector Directory Submission Checklist

**Submission form:** http://clau.de/mcp-directory-submission  
**Last updated:** 2026-05-12

Use this document as a ready-to-paste reference when filling out the MCP directory submission form. Fields marked `[TODO]` need to be completed before submitting.

---

## What Still Needs to Be Done Before Submitting

- [ ] Deploy Kynara to production Railway URL and replace the placeholder server URL below
- [ ] Finalize `kynaraai.com` domain and ensure docs, privacy policy, and support email are live
- [ ] Create SVG logo asset (square, ideally 256x256 minimum) and favicon (32x32 PNG or ICO)
- [ ] Take 2 polished screenshots of the Kynara dashboard/connector in use (1280x800 recommended)
- [ ] Create a dedicated reviewer test account and record credentials in a secure location
- [ ] Review Anthropic's connector approval guidelines for any last-minute policy changes

---

## 1. Server Basics

| Field | Value |
|---|---|
| **Server name** | Kynara |
| **Server URL** | `https://[RAILWAY-URL].up.railway.app` `[TODO: replace with production URL]` |
| **Tagline** | AI agent permission control plane — govern, audit, and approve agent actions |
| **Category** | Developer Tools / Security & Compliance |

### Description (2–3 sentences)

> Kynara is an AI agent permission control plane that lets teams define roles, enforce access policies, and approve or reject agent actions in real time. It provides a centralized audit log of every action taken by every agent, so compliance and security teams have full visibility across automated workflows. Connect Claude agents to Kynara via MCP to gate sensitive operations behind human-approval gates and role-based access controls.

### Use Cases

- Gate high-stakes agent actions (file deletion, API calls, data exports) behind human approval workflows
- Assign fine-grained roles to AI agents and check permissions before any action is executed
- Audit every agent action with timestamped logs for compliance and incident response
- Manage multi-agent systems by creating, monitoring, and killing agents from a single control plane

---

## 2. Connection Details

| Field | Value |
|---|---|
| **Auth type** | OAuth 2.0 — Authorization Code + PKCE |
| **Transport** | HTTP + SSE (Server-Sent Events) |
| **Authorization endpoint** | `/oauth/authorize` |
| **Token endpoint** | `/oauth/token` |
| **OAuth metadata URL** | `/.well-known/oauth-authorization-server` |
| **Scopes** | `read`, `write` |
| **Read capability** | Yes |
| **Write capability** | Yes |

---

## 3. Tools List (15 tools)

| Tool name (MCP identifier) | Human-readable name | Description |
|---|---|---|
| `kynara_list_agents` | List Agents | Retrieve all registered AI agents in the workspace |
| `kynara_get_agent` | Get Agent | Fetch details for a specific agent by ID |
| `kynara_create_agent` | Create Agent | Register a new AI agent in the permission system |
| `kynara_kill_agent` | Kill Agent | Immediately revoke all permissions and deactivate an agent |
| `kynara_get_agent_access_summary` | Get Agent Access Summary | View a full summary of what a specific agent is permitted to do |
| `kynara_check_permission` | Check Permission | Verify whether an agent is authorized to perform a given action |
| `kynara_list_approvals` | List Approval Requests | Retrieve all pending and resolved human-approval requests |
| `kynara_approve_request` | Approve Request | Approve a pending agent action request |
| `kynara_reject_request` | Reject Request | Reject a pending agent action request |
| `kynara_list_roles` | List Roles | Retrieve all roles defined in the workspace |
| `kynara_create_role` | Create Role | Define a new role with specific permissions |
| `kynara_update_role` | Update Role | Modify the permissions or metadata of an existing role |
| `kynara_delete_role` | Delete Role | Remove a role from the workspace |
| `kynara_assign_role` | Assign Role | Assign a role to a specific agent |
| `kynara_list_audit_logs` | List Audit Logs | Query the tamper-evident log of all agent actions |

**Total tool count:** 15

---

## 4. Data and Compliance

### Data Accessed

- Agent configurations (name, ID, status, assigned roles)
- Audit logs (action type, timestamp, outcome, agent identity)
- Approval requests (action details, requester, approver, decision)
- Role definitions (name, permissions, assignments)

### Personally Identifiable Information (PII)

- No user PII is accessed or stored beyond **email address and display name** used for authentication
- No browsing data, financial data, or sensitive personal data is collected

### Data Training

- User data is **not** used to train any AI or ML models

### Data Storage

- Primary data store: **PostgreSQL** hosted on **Railway** (US region)
- Data is not transferred outside of Railway infrastructure during normal operation

### Third-Party Services

| Service | Purpose |
|---|---|
| Stripe | Billing and subscription management |
| Resend | Transactional email delivery |
| Railway | Cloud infrastructure and database hosting |

---

## 5. Documentation and Support

| Field | Value |
|---|---|
| **Documentation URL** | `https://kynaraai.com/docs` `[TODO: ensure live before submission]` |
| **Privacy policy URL** | `https://kynaraai.com/privacy` |
| **Support email** | support@kynaraai.com |
| **Homepage** | `https://kynaraai.com` `[TODO: ensure live before submission]` |

---

## 6. Branding Assets

| Asset | Status | Notes |
|---|---|---|
| Logo (SVG) | `[TODO]` | Square format, min 256x256, transparent background preferred |
| Favicon | `[TODO]` | 32x32 PNG or ICO |
| Screenshot 1 | `[TODO]` | Show the agent list / permission dashboard (1280x800 recommended) |
| Screenshot 2 | `[TODO]` | Show an approval request being handled or the audit log view |

---

## 7. Reviewer Test Account

Provide the following to the Anthropic review team so they can test the connector end-to-end.

| Field | Value |
|---|---|
| **Sign-up URL** | `https://kynaraai.com` (create a free account) |
| **Test email** | `[TODO: create reviewer@kynaraai.com or a dedicated test account]` |
| **Test password** | `[TODO: set and record securely]` |
| **Pre-seeded data** | `[TODO: ensure account has at least 2 agents, 2 roles, and 1 pending approval for reviewer to interact with]` |

### Reviewer Instructions

1. Navigate to `https://kynaraai.com` and click **Sign Up** (or use the pre-created credentials above).
2. Connect Claude to Kynara via the MCP connector using OAuth — authorize with the test account.
3. Ask Claude to run `kynara_list_agents` to verify the connection.
4. Try `kynara_check_permission` with a sample agent ID and action.
5. View a pending approval with `kynara_list_approvals`, then call `kynara_approve_request` or `kynara_reject_request`.
6. Confirm the action appears in `kynara_list_audit_logs`.

---

## 8. Submission Readiness Checklist

### Before Hitting Submit

- [ ] Production Railway URL is live and stable
- [ ] OAuth flow tested end-to-end from a fresh Claude session
- [ ] All 15 MCP tools respond correctly against the production server
- [ ] `/.well-known/oauth-authorization-server` returns valid JSON metadata
- [ ] Documentation URL (`/docs`) is live and covers tool usage
- [ ] Privacy policy URL (`/privacy`) is live
- [ ] Logo SVG and favicon assets ready to upload
- [ ] 2 screenshots captured and ready to upload
- [ ] Test account created with seeded data for reviewer
- [ ] support@kynaraai.com inbox monitored and ready for reviewer follow-up

---

*This document is an internal reference only — do not commit credentials or private URLs to a public repository.*
