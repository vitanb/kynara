# Demo — Slack support agent refund → manager approval

A Slack AI support agent tries to refund a customer $89.00. Kynara's policy says any
refund over $50 needs a human, so it returns `require_approval` and the agent pauses
until a manager approves — then the refund executes and every step is recorded.

There's also an interactive web version at **`/demo/refund-approval`** on the site.

## Files
- `policy.json` — the policy: refunds over $50 (`amount_cents > 5000`) → `require_approval`.
- `demo.py` — runs the flow: check decision → pause → poll for approval → execute (or escalate).

## Run it offline (no server)
```bash
python demo.py --mock
# see the rejection branch:
DEMO_REJECT=1 python demo.py --mock
```

## Run it against a live Kynara
1. Create the policy from `policy.json` (Policies → New, or `POST /api/v1/policies`).
2. Make sure your agent's role grants `payments.refund.issue`.
3. Configure and run:
```bash
pip install requests
export KYNARA_API_BASE_URL="https://kynaraai.com"
export KYNARA_API_KEY="sk_live_..."
export KYNARA_AGENT_ID="<your slack-support-agent id>"
python demo.py
```
The script blocks on `require_approval`; approve or reject it in the Kynara UI (Approvals)
or from Slack, and the script continues.

## What it shows
- **Least privilege in action** — the agent can read and draft, but a money-moving action is gated.
- **Human-in-the-loop** — `require_approval` pauses the agent before the side effect runs.
- **Fail-closed** — if approval never comes (timeout), the refund is not executed.
- **Audit** — request, decision, approver, and execution are all recorded in the tamper-evident log.
