import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { CreditCard, TrendingUp, FileText, ExternalLink, Zap, Shield, Building2, X, Check, Users, AlertTriangle, Clock } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── plan definitions ────────────────────────────────────────────────────────
const PLANS = [
  {
    id: "pro",
    name: "Pro",
    price: "$49",
    period: "per seat / month",
    icon: Shield,
    iconColor: "var(--s0-accent)",
    iconBg: "var(--s0-accent-ring)",
    features: [
      "Up to 10 seats",
      "50,000 policy decisions / month",
      "Unlimited AI agents",
      "Audit log (1 year retention)",
      "SSO / OIDC support",
      "Custom roles & scopes",
      "Email support with 24h SLA",
    ],
    highlighted: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    period: "annual contract",
    icon: Building2,
    iconColor: "#F59E0B",
    iconBg: "rgba(245,158,11,0.12)",
    features: [
      "Everything in Pro",
      "SAML 2.0 & SCIM",
      "Unlimited decisions",
      "On-prem / private cloud",
      "Dedicated Slack support",
      "99.99% uptime SLA",
    ],
    highlighted: false,
  },
];

export default function BillingPage() {
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState("pro");

  const { data: sub } = useQuery({
    queryKey: ["billing", "sub"],
    queryFn: () => api.get<any>("/api/v1/billing/subscription"),
  });
  const { data: usage } = useQuery({
    queryKey: ["billing", "usage"],
    queryFn: () => api.get<any>("/api/v1/billing/usage"),
  });
  const { data: invoices = [] } = useQuery({
    queryKey: ["billing", "invoices"],
    queryFn: () => api.get<any[]>("/api/v1/billing/invoices"),
  });

  // Seat usage from org members list
  const { data: members = [] } = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<any[]>("/api/v1/org/members"),
  });

  const pct = usage
    ? Math.min(100, Math.round((usage.decisions_used / (usage.decisions_included || 1)) * 100))
    : 0;

  const seatsUsed = members.length;
  const seatsIncluded = sub?.seats_included ?? 3;
  const seatPct = Math.min(100, Math.round((seatsUsed / seatsIncluded) * 100));

  const isOnFree = sub?.plan === "free" || sub?.plan === "trial" || !sub?.plan;
  const isOnPaid = !isOnFree && sub?.plan !== "enterprise";
  const isTrialing = sub?.status === "trialing";
  const trialDaysLeft = sub?.current_period_end
    ? Math.max(0, Math.ceil((new Date(sub.current_period_end).getTime() - Date.now()) / 86_400_000))
    : null;

  const portal = useMutation({
    mutationFn: () =>
      api.post<{ redirect_url: string }>("/api/v1/billing/portal", {}),
    onSuccess: ({ redirect_url }) => {
      window.location.href = redirect_url;
    },
    onError: () => {
      window.open("mailto:support@kynara.ai?subject=Manage subscription", "_blank");
    },
  });

  const checkout = useMutation({
    mutationFn: () =>
      api.post<{ redirect_url: string }>("/api/v1/billing/checkout", {
        plan: selectedPlan,
        success_url: `${window.location.origin}/app/billing?success=1`,
        cancel_url: `${window.location.origin}/app/billing`,
      }),
    onSuccess: ({ redirect_url }) => {
      window.location.href = redirect_url;
    },
    onError: () => {
      // Stripe not configured — open contact sales
      window.open("mailto:sales@kynara.ai?subject=Upgrade inquiry", "_blank");
    },
  });

  return (
    <div>
      <PageHeader
        title="Billing"
        subtitle="Plan, usage, and invoice history. Usage is metered nightly."
      />

      <div className="px-8 py-6 space-y-4">

        {/* ── Trial / quota warning banners ── */}
        {isTrialing && trialDaysLeft !== null && (
          <div className="rounded-xl px-4 py-3 flex items-center gap-3 text-sm"
            style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)" }}>
            <Clock className="size-4 shrink-0 text-warn-400" />
            <span className="text-warn-300">
              <strong>Free trial:</strong> {trialDaysLeft} day{trialDaysLeft !== 1 ? "s" : ""} remaining.
              After the trial your org stays on the free plan (3 seats · 10k decisions/month).
            </span>
            <button className="ml-auto btn-primary py-1 px-3 text-xs shrink-0" onClick={() => setUpgradeOpen(true)}>
              Upgrade now
            </button>
          </div>
        )}

        {pct >= 90 && (
          <div className="rounded-xl px-4 py-3 flex items-center gap-3 text-sm"
            style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)" }}>
            <AlertTriangle className="size-4 shrink-0 text-danger-400" />
            <span className="text-danger-300">
              <strong>Decision quota {pct >= 100 ? "exhausted" : "nearly full"}:</strong>{" "}
              {pct >= 100
                ? "All decisions are being blocked. Upgrade to continue."
                : `${pct}% of your monthly decisions used. Upgrade before you hit the limit.`}
            </span>
            <button className="ml-auto btn-primary py-1 px-3 text-xs shrink-0" onClick={() => setUpgradeOpen(true)}>
              Upgrade
            </button>
          </div>
        )}

        {seatPct >= 100 && (
          <div className="rounded-xl px-4 py-3 flex items-center gap-3 text-sm"
            style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)" }}>
            <Users className="size-4 shrink-0 text-danger-400" />
            <span className="text-danger-300">
              <strong>Seat limit reached:</strong> You cannot add more members until you upgrade.
            </span>
            <button className="ml-auto btn-primary py-1 px-3 text-xs shrink-0" onClick={() => setUpgradeOpen(true)}>
              Upgrade
            </button>
          </div>
        )}

        {/* ── Top row: Plan + Usage ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* Plan card */}
          <div className="card p-5 flex flex-col">
            <div className="flex items-center gap-2 text-sm font-medium mb-4">
              <CreditCard className="size-4 text-accent-500" /> Current plan
            </div>
            <div className="flex items-center gap-3 mb-4">
              <div className="size-10 rounded-xl flex items-center justify-center"
                style={{ background: "var(--s0-accent-ring)" }}>
                <Zap className="size-5" style={{ color: "var(--s0-accent)" }} />
              </div>
              <div>
                <div className="text-2xl font-bold text-ink-50 capitalize">{sub?.plan || "Free"}</div>
                <div className="text-xs text-ink-400 capitalize">status · {sub?.status || "active"}</div>
              </div>
            </div>

            <div className="space-y-2 text-xs text-ink-300 mb-5 flex-1">
              <div className="flex justify-between">
                <span className="text-ink-500">Seats included</span>
                <span className="font-mono">{sub?.seats_included ?? 3}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-500">Decisions / month</span>
                <span className="font-mono">{sub?.decisions_included?.toLocaleString() ?? "10,000"}</span>
              </div>
              {sub?.current_period_end && (
                <div className="flex justify-between">
                  <span className="text-ink-500">Period ends</span>
                  <span className="font-mono">{new Date(sub.current_period_end).toLocaleDateString()}</span>
                </div>
              )}
            </div>

            {isOnFree ? (
              <button className="btn-primary w-full justify-center" onClick={() => setUpgradeOpen(true)}>
                Upgrade plan
              </button>
            ) : isOnPaid ? (
              <button
                className="w-full justify-center py-2 text-sm text-ink-400 hover:text-ink-50 transition-colors disabled:opacity-50"
                disabled={portal.isPending}
                onClick={() => portal.mutate()}
              >
                {portal.isPending ? "Opening…" : "Manage subscription"}
              </button>
            ) : (
              <button
                className="w-full justify-center py-2 text-sm text-ink-400 hover:text-ink-50 transition-colors"
                onClick={() => window.open("mailto:sales@kynara.ai", "_blank")}
              >
                Contact sales
              </button>
            )}
          </div>

          {/* Usage card */}
          <div className="card p-5 lg:col-span-2">
            <div className="flex items-center gap-2 text-sm font-medium mb-4">
              <TrendingUp className="size-4 text-accent-500" /> Usage this period
            </div>

            <div className="flex items-end justify-between mb-2">
              <div>
                <span className="text-3xl font-bold text-ink-50 tabular-nums">
                  {usage?.decisions_used?.toLocaleString() ?? "0"}
                </span>
                <span className="text-sm text-ink-400 font-normal ml-2">
                  / {usage?.decisions_included?.toLocaleString() ?? "10,000"} decisions
                </span>
              </div>
              <span className={`text-sm font-semibold tabular-nums ${
                pct >= 90 ? "text-danger-400" : pct >= 70 ? "text-warn-400" : "text-ok-400"
              }`}>{pct}%</span>
            </div>

            {/* Decisions progress bar */}
            <div className="h-2 rounded-full overflow-hidden mb-4"
              style={{ background: "rgba(148,163,184,0.1)" }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: pct + "%",
                  background: pct >= 90 ? "#F43F5E" : pct >= 70 ? "#F59E0B" : "#10B981",
                }}
              />
            </div>

            {/* Seat usage */}
            <div className="flex items-end justify-between mb-2">
              <div className="flex items-center gap-2">
                <Users className="size-3.5 text-ink-500" />
                <span className="text-sm text-ink-400">
                  <span className="font-bold text-ink-50 tabular-nums">{seatsUsed}</span>
                  {" "}/ {seatsIncluded} seats used
                </span>
              </div>
              <span className={`text-xs font-semibold tabular-nums ${
                seatPct >= 100 ? "text-danger-400" : seatPct >= 66 ? "text-warn-400" : "text-ok-400"
              }`}>{seatPct}%</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden mb-4"
              style={{ background: "rgba(148,163,184,0.1)" }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: seatPct + "%",
                  background: seatPct >= 100 ? "#F43F5E" : seatPct >= 66 ? "#F59E0B" : "#10B981",
                }}
              />
            </div>

            <div className="grid grid-cols-3 gap-4 text-xs">
              <div className="rounded-lg p-3" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.08)" }}>
                <div className="text-ink-500 mb-1">Period start</div>
                <div className="text-ink-200 font-mono">
                  {usage?.period_start ? new Date(usage.period_start).toLocaleDateString() : "—"}
                </div>
              </div>
              <div className="rounded-lg p-3" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.08)" }}>
                <div className="text-ink-500 mb-1">Period end</div>
                <div className="text-ink-200 font-mono">
                  {usage?.period_end ? new Date(usage.period_end).toLocaleDateString() : "—"}
                </div>
              </div>
              <div className="rounded-lg p-3" style={{
                background: usage?.overage_decisions ? "rgba(244,63,94,0.08)" : "rgba(148,163,184,0.05)",
                border: usage?.overage_decisions ? "1px solid rgba(244,63,94,0.2)" : "1px solid rgba(148,163,184,0.08)",
              }}>
                <div className="text-ink-500 mb-1">Overage</div>
                <div className={`font-mono ${usage?.overage_decisions ? "text-danger-400" : "text-ink-200"}`}>
                  {usage?.overage_decisions?.toLocaleString() || "0"} decisions
                </div>
                {usage?.overage_amount_cents > 0 && (
                  <div className="text-danger-400 text-[10px] mt-0.5">
                    ~${(usage.overage_amount_cents / 100).toFixed(2)} estimated
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── Invoices ── */}
        <div className="card overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-ink-800">
            <FileText className="size-4 text-accent-500" />
            <span className="text-sm font-medium">Invoice history</span>
          </div>
          {invoices.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Period</th><th>Amount</th><th>Status</th><th>Invoice</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv: any) => (
                  <tr key={inv.id}>
                    <td className="text-xs text-ink-300">
                      {inv.period_start ? new Date(inv.period_start).toLocaleDateString() : "—"}
                      {" — "}
                      {inv.period_end ? new Date(inv.period_end).toLocaleDateString() : "—"}
                    </td>
                    <td className="font-mono text-sm">
                      ${((inv.amount_cents || 0) / 100).toFixed(2)}{" "}
                      <span className="text-xs text-ink-500 uppercase">{inv.currency}</span>
                    </td>
                    <td>
                      <span className={inv.status === "paid" ? "pill-ok" : "pill-warn"}>
                        {inv.status}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        {inv.hosted_url && (
                          <a href={inv.hosted_url} target="_blank" rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-accent-500 hover:underline">
                            View <ExternalLink className="size-3" />
                          </a>
                        )}
                        {inv.pdf_url && (
                          <a href={inv.pdf_url} target="_blank" rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-ink-400 hover:text-ink-50">
                            PDF <ExternalLink className="size-3" />
                          </a>
                        )}
                        {!inv.hosted_url && !inv.pdf_url && (
                          <span className="text-xs text-ink-600">—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="py-12 text-center">
              <FileText className="size-8 mx-auto mb-3 text-ink-700" />
              <p className="text-sm text-ink-400">No invoices yet.</p>
              <p className="text-xs text-ink-600 mt-1">
                Invoices appear here after each billing cycle.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Upgrade plan modal ── */}
      {upgradeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden"
            style={{ background: "var(--s0-card)", border: "1px solid rgba(148,163,184,0.12)" }}>

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5"
              style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <div>
                <div className="text-lg font-semibold text-ink-50">Upgrade your plan</div>
                <div className="text-xs text-ink-400 mt-0.5">
                  Unlock more agents, decisions, and SSO.
                </div>
              </div>
              <button onClick={() => setUpgradeOpen(false)}
                className="text-ink-400 hover:text-ink-50 transition-colors">
                <X className="size-5" />
              </button>
            </div>

            {/* Plan grid */}
            <div className="p-6 grid sm:grid-cols-2 gap-4">
              {PLANS.map((plan) => {
                const Icon = plan.icon;
                const isSelected = selectedPlan === plan.id;
                return (
                  <button
                    key={plan.id}
                    onClick={() => setSelectedPlan(plan.id)}
                    className="rounded-xl p-5 text-left transition-all"
                    style={{
                      background: isSelected ? "var(--s0-accent-subtle)" : "rgba(148,163,184,0.04)",
                      border: isSelected
                        ? "1px solid var(--s0-accent-ring)"
                        : "1px solid rgba(148,163,184,0.1)",
                    }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="size-8 rounded-lg flex items-center justify-center"
                        style={{ background: plan.iconBg }}>
                        <Icon className="size-4" style={{ color: plan.iconColor }} />
                      </div>
                      {isSelected && (
                        <div className="size-5 rounded-full flex items-center justify-center"
                          style={{ background: "var(--s0-accent)" }}>
                          <Check className="size-3 text-ink-50" />
                        </div>
                      )}
                    </div>
                    <div className="text-base font-bold text-ink-50 mb-0.5">{plan.name}</div>
                    <div className="text-ink-400 text-xs mb-3">
                      <span className="text-xl font-bold text-ink-50">{plan.price}</span>
                      {" "}{plan.period}
                    </div>
                    <ul className="space-y-1.5">
                      {plan.features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-xs text-ink-300">
                          <Check className="size-3 mt-0.5 shrink-0 text-ok-500" /> {f}
                        </li>
                      ))}
                    </ul>
                  </button>
                );
              })}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between gap-3 px-6 py-4"
              style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
              <p className="text-xs text-ink-500">
                {selectedPlan === "enterprise"
                  ? "We'll reach out to discuss pricing and setup."
                  : "You'll be redirected to Stripe to complete payment. No charge until confirmed."}
              </p>
              <div className="flex items-center gap-3 shrink-0">
                <button className="btn-ghost" onClick={() => setUpgradeOpen(false)}>Cancel</button>
                <button
                  className="btn-primary"
                  disabled={checkout.isPending}
                  onClick={() => checkout.mutate()}
                >
                  {checkout.isPending
                    ? "Redirecting…"
                    : selectedPlan === "enterprise"
                    ? "Contact sales"
                    : "Continue to checkout →"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
