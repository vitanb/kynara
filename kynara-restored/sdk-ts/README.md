# @kynara/sdk

TypeScript / Node SDK for [Kynara](https://kynara.example.com) — runtime authorization for AI agents.

```bash
npm install @kynara/sdk
```

## Quickstart

```ts
import { Kynara, guarded, PermissionDenied, ApprovalRequired } from "@kynara/sdk";

const client = Kynara.fromEnv(); // reads KYNARA_BASE_URL, KYNARA_API_KEY, KYNARA_AGENT_ID

const issueRefund = guarded({
  client,
  action: "payments.refund.issue",
  resource: (refundId: string, amountCents: number) => ({
    type: "payment.refund",
    id: refundId,
    attrs: { amount_cents: amountCents, currency: "USD" },
  }),
  context: () => ({ ip_country: "US" }),
}, async (refundId: string, amountCents: number) => {
  return await processRefund(refundId, amountCents);
});

try {
  await issueRefund("r_123", 500_00);
} catch (e) {
  if (e instanceof ApprovalRequired) {
    notifyApprover(e.approvalUrl);
  } else if (e instanceof PermissionDenied) {
    auditDeny(e.decision.reason);
  } else throw e;
}
```

## Express middleware

```ts
import { requirePermission } from "@kynara/sdk/express";
app.post("/refunds/:id",
  requirePermission({
    client,
    action: "payments.refund.issue",
    resource: (req) => ({ type: "payment.refund", id: req.params.id, attrs: req.body }),
  }),
  refundController);
```

## LangChain.js

```ts
import { KynaraCallbackHandler } from "@kynara/sdk/langchain";
const executor = new AgentExecutor({
  agent, tools,
  callbacks: [new KynaraCallbackHandler(client, "agent_crm_assistant")],
});
```

The handler maps every tool start through `client.enforce(...)` — `deny` and
`require_approval` raise typed errors with `decision_id` and `approval_url`.

## Fail-closed

Default behaviour when Kynara is unreachable is to **deny** with reason
`"fail-closed: kynara unreachable"`. This mirrors the Python SDK and the
backend's own default. Set `failClosed: false` on the client only if you have
a compelling availability reason and accept the security trade-off.
