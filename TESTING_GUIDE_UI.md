# Kynara — UI Testing Guide

A step-by-step walkthrough for testing every major workflow in Kynara using the browser UI.
No command line required.

---

## Prerequisites

- Kynara is deployed and accessible (Railway or local)
- You are signed in as an **owner** or **admin**
- Default demo credentials: `admin@demo.kynara.dev` / `kynara-demo`

---

## Step 1 — Register an Agent

1. Click **Agents** in the left sidebar
2. Click **+ New Agent** (top right)
3. Fill in the form:
   - **Name** — e.g. `My Test Agent`
   - **Slug** — auto-filled, e.g. `my-test-agent`
   - **Description** — e.g. `Test agent for Kynara walkthrough`
   - **Mode** — choose `human_supervised` or `autonomous`
   - **Model** — e.g. `claude-sonnet-4-6`
   - **Daily action budget** — e.g. `1000`
4. Click **Create Agent**
5. You land on the agent detail page — copy the **Agent ID** (UUID in the URL or next to the copy icon)

> **Save these values:**
> - Agent ID (UUID)
> - The org's API key (created in Step 2)

---

## Step 2 — Create an API Key

1. Click **Settings** → **API Keys** tab
2. Click **+ New API Key**
3. Give it a name, e.g. `Test Key`
4. Set the role to **developer** or **admin**
5. Click **Create**
6. **Copy the key immediately** — it is shown only once
7. Store it as `KYNARA_API_KEY` for use in API calls

---

## Step 3 — Register Tools in the Scope Catalog

> The **Tools** page is now called **Scope Catalog**.

1. Click **Scope Catalog** in the left sidebar
2. Click **+ New Tool**
3. Fill in:
   - **Namespace** — e.g. `payments`
   - **Name** — e.g. `refund.issue`
   - **Description** — e.g. `Issue a refund to a customer`
   - **Risk class** — choose `critical`
   - **Input schema** (JSON):
     ```json
     {
       "type": "object",
       "properties": {
         "payment_id": { "type": "string" },
         "amount_cents": { "type": "integer" }
       }
     }
     ```
   - **Scope** — e.g. `payments.refund.issue`
4. Click **Save**

Repeat to create a second tool:
- Namespace: `crm` | Name: `contacts.read` | Risk class: `low` | Scope: `crm.contacts.read`

---

## Step 4 — Create a Policy

1. Click **Policies** in the left sidebar
2. Click **+ New Policy**
3. Fill in:
   - **Name** — e.g. `Deny off-hours refunds`
   - **Effect** — choose `require_approval`
   - **Priority** — `100`
   - **Actions** — `payments.refund.issue`
   - **Condition** (JSON):
     ```json
     {
       "op": "not",
       "args": [
         { "op": "time_between", "args": ["ctx.context.time", "09:00", "18:00"] }
       ]
     }
     ```
4. Click **Save**

Create a second policy:
- **Name** — `Deny autonomous high-risk`
- **Effect** — `deny`
- **Priority** — `50`
- **Actions** — `payments.*`
- **Condition**:
  ```json
  { "op": "eq", "args": ["ctx.subject.attrs.mode", "autonomous"] }
  ```

---

## Step 5 — Test a Policy with the Integrated Simulator

> The Policy Simulator is now embedded inside the Policy Editor — there is no separate Simulator nav item.

1. Click **Policies** → open any policy
2. Scroll down to the **Simulator** panel within the policy editor
3. Fill in:
   - **Agent** — select your test agent
   - **Action** — `payments.refund.issue`
   - **Resource type** — `payment`
   - **Context** — e.g. `{ "ip": "1.2.3.4", "time": "03:00" }`
4. Click **Evaluate**
5. The result shows `allow`, `deny`, or `require_approval` with the matching policy name and granted scopes

---

## Step 6 — Run a Policy Historical Replay

Policy Replay lets you simulate the impact of a new or changed policy against real past decisions before deploying it.

1. Click **Policies** → open a policy or click **+ New Policy**
2. Fill in the policy details (effect, actions, condition)
3. Click **Replay against history** (below the condition editor)
4. Choose a **lookback window** (e.g. 14 days)
5. Click **Run Replay**
6. Review the results:
   - Total events evaluated
   - How many decisions would flip (allow → deny, allow → require_approval, etc.)
   - Sample affected decision IDs you can click to inspect
7. If the impact looks acceptable, click **Save** to deploy

---

## Step 7 — Bind a Policy and Assign a Role to an Agent

1. Open the policy → click **Bindings** tab
2. Click **+ Add Binding** → set Subject selector to `*` (all agents) or `agent:<agent-id>`
3. Click **Save Binding**

Then assign the agent a role:

1. Click **Agents** → open your test agent → **Assignments** tab
2. Click **+ Add Assignment** → select a User and a Role
3. Click **Save**

---

## Step 8 — Call the Decision API

Test from any REST client (Postman, curl, browser DevTools):

**Endpoint:**
```
POST /api/v1/decisions/check
```

**Headers:**
```
Authorization: Bearer <KYNARA_API_KEY>
Content-Type: application/json
```

**Body:**
```json
{
  "agent_id": "<your-agent-id>",
  "action": "payments.refund.issue",
  "resource_type": "payment",
  "resource_id": "pay_123",
  "context": { "ip": "1.2.3.4", "time": "03:00" },
  "inputs": { "payment_id": "pay_123", "amount_cents": 5000 }
}
```

**Expected responses:**

| Scenario | Response |
|---|---|
| Action allowed | `{ "decision": "allow" }` |
| Denied by policy | `{ "decision": "deny", "reason": "Deny autonomous high-risk" }` |
| Approval required | `{ "decision": "require_approval", "approval_id": "<uuid>", "approval_url": "..." }` |

---

## Step 9 — Approve or Deny a Pending Request

1. Click **Approvals** in the left sidebar
2. Find the pending request — shows agent name, action, resource, context, risk score
3. Review the details:
   - What action was requested and which policy triggered it
   - The inputs the agent passed
   - Historical denial rate for this agent + action
4. Click **Approve** or **Deny**, enter a justification
5. The agent can poll `GET /api/v1/approvals/<approval_id>` to check status

---

## Step 10 — Create a JIT Grant (Break-Glass Access)

JIT grants give an agent or user a temporary elevated permission without changing any policy.

1. Click **JIT Grants** in the left sidebar (or navigate to **Settings → JIT Grants**)
2. Click **+ New Grant**
3. Fill in:
   - **Scope** — e.g. `crm:write`
   - **Duration** — e.g. `120 minutes`
   - **Justification** — e.g. `Investigating prod escalation`
   - **Ticket URL** — e.g. `https://jira.example.com/TICKET-42`
4. Click **Create Grant**
5. The grant is immediately active — the agent's effective scopes now include `crm:write`
6. The grant appears in the Audit Log with `event_type = jit_grant.created`
7. To revoke early: open the grant → click **Revoke**

---

## Step 11 — Set Up a Guardrail

Guardrails watch live agent events and auto-revoke access when thresholds are breached.

1. Click **Guardrails** in the left sidebar
2. Click **+ New Integration** → copy the **Webhook URL**
3. Your agent POSTs events to this URL (from its own runtime)
4. Click **Rules** tab → **+ New Rule**
5. Configure:
   - **Threshold** — `5 events`
   - **Time window** — `5 minutes`
   - **Severity filter** — `high`, `critical`
   - **Action** — `revoke`
6. Click **Save Rule**

When 5+ high/critical events arrive within 5 minutes, Kynara automatically revokes the agent. An `agent.killed` webhook fires immediately.

---

## Step 12 — View the Audit Log

1. Click **Audit** in the left sidebar
2. Every decision, approval, JIT grant, and admin change is listed with:
   - Timestamp, agent name, action, outcome, matched policy
3. Use filters to narrow by agent, date range, event type, or outcome
4. Click **Verify Chain** to run the SHA-256 integrity check — a green banner confirms the chain is unbroken
5. To export: click **Export CSV** (top right) — downloads a CSV of the filtered view
6. For SIEM ingestion: use the polling cursor API (`GET /api/v1/audit/events?after_cursor=<cursor>`) to stream events into Splunk, Datadog, or Elastic

---

## Step 13 — Set Up Webhooks

1. Click **Settings** → **Webhooks** tab
2. Click **+ New Webhook**
3. Enter your endpoint URL and select the events to subscribe to:
   - `decision.denied`
   - `decision.approval_requested`
   - `decision.approved`
   - `agent.killed`
   - `policy.changed`
   - `audit.chain_broken`
   - `permissions_changed`
4. Click **Save**
5. Click **Send Test Event** to verify your endpoint receives and verifies the HMAC signature

---

## Step 14 — Manage Members and Pending Invites

1. Click **Settings** → **Members** tab
2. To invite: click **+ Invite member**, enter email, select role, click **Send**
3. The invite appears in the **Pending Invites** section until the recipient accepts
4. To resend or cancel a pending invite: click the **...** menu next to the invite
5. To change a role: click the role badge next to any active member
6. To remove a member: click **Remove** → confirm

---

## Step 15 — SSO Configuration (Enterprise)

1. Click **Settings** → **SSO** tab
2. Click **+ New SSO Connection**
3. Choose provider: **Okta**, **Google Workspace**, **Azure AD**, or **Generic SAML**
4. Follow the provider-specific wizard (redirect URIs and SP metadata are auto-generated)
5. Click **Test Connection** before enabling
6. Multiple SSO connections can coexist — useful for org mergers or multi-IdP environments

---

## Step 16 — SIEM Integration (Splunk / Datadog / Elastic)

1. Click **Settings** → **Integrations** or **Audit** → **SIEM Setup**
2. Follow the guided setup for your SIEM:
   - **Splunk**: install the Kynara Add-on, configure the polling cursor URL + API key
   - **Datadog**: configure the Log Pipeline with the polling cursor endpoint
   - **Elastic**: install the Filebeat module with the cursor endpoint
3. The cursor API is stateless — store `next_cursor` from each response and pass it as `after_cursor` on the next call

---

## Step 17 — Superadmin: Platform Management

> Only accounts with the superadmin flag can access this section.

1. In the top-right user menu, click **Admin Console** (visible only to superadmins)
2. The Admin Console shows:
   - All organizations on the platform with member counts and plan details
   - All users across all orgs
3. To create a new org: click **+ New Organization**
4. To invite a member to any org: click the org → **Invite Member**
5. All superadmin actions are recorded with `event_type = admin.superadmin.*` in the audit log

---

## Step 18 — Danger Zone (Settings)

1. Click **Settings** → scroll to **Danger Zone**
2. Options available:
   - **Rotate API keys** — immediately invalidates all existing API keys and issues new ones
   - **Revoke all sessions** — signs out all active users (useful after a suspected compromise)
   - **Delete organization** — permanently deletes the org and all data (irreversible; requires typing the org name to confirm)

---

## Step 19 — View the Trust Center

1. Navigate to `https://your-kynara-domain/trust`
2. The Trust Center displays customer-shareable compliance evidence:
   - SOC 2 Type II status
   - ISO 27001 certification status
   - GDPR/HIPAA documentation availability
   - Pen test date and scope
   - Service status link
3. Share this URL with customers and partners during security reviews

---

## Quick Reference — Default Demo Data

| Item | Value |
|---|---|
| Admin email | `admin@demo.kynara.dev` |
| Admin password | `kynara-demo` |
| Demo org slug | `acme` |
| Demo agent | `CRM Assistant` (crm-assistant) |
| Demo agent 2 | `Support Triage` (support-triage) |
| Demo tools | `crm.contacts.read`, `email.send`, `payments.refund.issue` |
| Demo policies | Deny off-hours refunds, Deny autonomous high-risk, Allow CRM reads EU |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Sign-in fails | Check backend is running; verify `DATABASE_URL` points to correct Postgres |
| Scope Catalog blank | Seed script didn't run; check backend logs for `Seeded demo org` |
| Decision always allows | No policy bindings — go to Policies and add a binding to `*` |
| Approval never appears | Policy effect must be `require_approval`, not `allow` or `deny` |
| API returns 401 | API key is wrong or revoked; generate a new one in Settings → API Keys |
| Policy Simulator not visible | It lives inside the Policy Editor — open any policy and scroll down |
| JIT Grant not widening access | Grant may have expired; check the JIT Grants list for status |
| Replay returns 0 events | No audit events in the lookback window yet; run some decisions first |
| Webhook not receiving | Verify HMAC signature logic; check endpoint returns 2xx within 5s |
| Plan quota reached | Decision endpoint returns `deny` with reason `quota_exceeded`; upgrade plan in Billing |
| Debug DB endpoint | `GET /api/v1/debug/db` — shows connected Postgres and row counts |
