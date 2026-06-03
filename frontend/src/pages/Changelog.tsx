export default function ChangelogPage() {
  const entries = [
    {
      version: "2.2", date: "May 2026", badge: "Latest",
      items: [
        { type: "new", text: "Slack & Teams approval integration — approve/reject directly from chat" },
        { type: "new", text: "PagerDuty alerts for agent.killed, audit.chain_broken, and anomaly events" },
        { type: "new", text: "Email approval notifications with one-click approve/reject links" },
        { type: "new", text: "Approval analytics — resolution times, rates, trends, top agents" },
        { type: "new", text: "Integrations page at top-level nav (Slack, Teams, PagerDuty, Email)" },
        { type: "new", text: "Industry solution pages: Healthcare, Manufacturing, DevOps, SecOps, FinServ" },
        { type: "new", text: "Free MCP Permission Inspector + Policy Sandbox (no signup)" },
        { type: "fix", text: "Rate limits on all auth endpoints (login 10/min, register 5/min)" },
        { type: "fix", text: "API key hashing upgraded to HMAC-SHA256" },
        { type: "fix", text: "Webhook URLs validated against SSRF blocklist before storage" },
        { type: "fix", text: "Password minimum raised to 12 characters" },
        { type: "fix", text: "Webhook signature format corrected to sha256=v1,<hex>" },
      ],
    },
    {
      version: "2.1", date: "Apr 2026",
      items: [
        { type: "new", text: "Policy Replay — simulate policy changes against 30 days of real decisions" },
        { type: "new", text: "JIT grants — time-bound break-glass permission elevations" },
        { type: "new", text: "Guardrails — threshold-based auto-revocation for runaway agents" },
        { type: "new", text: "Go sidecar for sub-millisecond local enforcement" },
        { type: "new", text: "TypeScript SDK with guarded() wrappers and Express middleware" },
        { type: "new", text: "Policy-as-code CLI (pull/push/diff/verify)" },
        { type: "new", text: "Scope Catalog (formerly Tools) with risk levels and input schemas" },
        { type: "new", text: "Webhook subscriptions with HMAC-signed delivery" },
        { type: "new", text: "SCIM 2.0 user provisioning" },
      ],
    },
    {
      version: "2.0", date: "Mar 2026",
      items: [
        { type: "new", text: "ABAC condition engine — time, geo, amount, environment conditions" },
        { type: "new", text: "Human-in-the-loop approval workflows with expiry and escalation" },
        { type: "new", text: "SHA-256 hash-chained tamper-evident audit log" },
        { type: "new", text: "Okta OIDC and SAML 2.0 SSO" },
        { type: "new", text: "Stripe billing integration with seat and decision quotas" },
        { type: "new", text: "Anomaly detection — deny-rate z-score and geo-jump alerting" },
        { type: "new", text: "LangChain, AutoGen, CrewAI, OpenAI, Anthropic SDK integrations" },
      ],
    },
    {
      version: "1.0", date: "Jan 2026",
      items: [
        { type: "new", text: "Initial release — RBAC policy engine, agent identities, multi-tenant" },
        { type: "new", text: "Python SDK with decorator and context manager" },
        { type: "new", text: "Dashboard, Agents, Policies, Audit log, Billing pages" },
        { type: "new", text: "JWT auth with rotating refresh tokens" },
      ],
    },
  ];

  const tagStyle: Record<string, React.CSSProperties> = {
    new:  { background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)", border: "1px solid var(--s0-accent-ring)" },
    fix:  { background: "rgba(16,185,129,.1)",  color: "#34D399", border: "1px solid rgba(16,185,129,.25)" },
    improved: { background: "rgba(245,158,11,.1)", color: "#FCD34D", border: "1px solid rgba(245,158,11,.25)" },
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-xl font-bold text-ink-50 mb-1">Changelog</h1>
      <p className="text-sm text-ink-400 mb-8">New features, fixes, and improvements.</p>
      <div className="space-y-10">
        {entries.map((entry) => (
          <div key={entry.version}>
            <div className="flex items-center gap-3 mb-4">
              <span className="text-base font-bold text-ink-50">v{entry.version}</span>
              {entry.badge && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(45,212,191,.12)", color: "#2DD4BF", border: "1px solid rgba(45,212,191,.3)" }}>
                  {entry.badge}
                </span>
              )}
              <span className="text-xs text-ink-400">{entry.date}</span>
            </div>
            <div className="space-y-2 border-l pl-4" style={{ borderColor: "rgba(148,163,184,.1)" }}>
              {entry.items.map((item, i) => (
                <div key={i} className="flex items-start gap-2.5">
                  <span className="inline-flex text-[10px] font-bold px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0"
                    style={tagStyle[item.type] || tagStyle.new}>
                    {item.type.toUpperCase()}
                  </span>
                  <span className="text-sm text-ink-300">{item.text}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
