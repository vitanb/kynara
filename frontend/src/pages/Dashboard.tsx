import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Bot, CheckCircle2, XCircle, AlertTriangle, TrendingUp,
  ArrowRight, ShieldCheck, FileText, Plus, Zap, Download, BarChart2,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── Design tokens ──────────────────────────────────────────────────────────
const C = {
  allow:   "#10B981",
  approve: "#F59E0B",
  deny:    "#F43F5E",
  accent:  "var(--s0-accent)",
  teal:    "#2DD4BF",
  quota:   "#2DD4BF",
};

type Tone = "ok" | "warn" | "danger" | "info";
const TONE: Record<Tone, { text: string; iconColor: string; bg: string; border: string }> = {
  ok:     { text: "text-ok-400",     iconColor: C.allow,   bg: "rgba(16,185,129,0.09)",  border: "rgba(4,120,87,0.25)" },
  warn:   { text: "text-warn-400",   iconColor: C.approve, bg: "rgba(245,158,11,0.09)",  border: "rgba(180,83,9,0.25)" },
  danger: { text: "text-danger-400", iconColor: C.deny,    bg: "rgba(244,63,94,0.09)",   border: "rgba(190,18,60,0.25)" },
  info:   { text: "text-accent-400", iconColor: C.accent,  bg: "var(--s0-accent-subtle)",  border: "var(--s0-accent-ring)" },
};

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtN(n: number) {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000 ? `${(n / 1_000).toFixed(1)}k`
    : String(n);
}

function pct(used: number, total: number) {
  if (!total) return 0;
  return Math.min(100, Math.round((used / total) * 100));
}

function dayLabel(d: Date) {
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// ── QuotaMeter ─────────────────────────────────────────────────────────────
function QuotaMeter({ used, total, label, color }: {
  used: number; total: number; label: string; color: string;
}) {
  const p = pct(used, total);
  const tone = p >= 90 ? C.deny : p >= 70 ? C.approve : color;
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5 text-xs">
        <span className="text-ink-300 font-medium">{label}</span>
        <span className="text-ink-200 tabular-nums font-semibold">
          {fmtN(used)}<span className="text-ink-500 font-normal"> / {fmtN(total)}</span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-ink-700 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${p}%`, background: tone }} />
      </div>
      <div className="mt-1 text-[10px] text-ink-500 tabular-nums">{p}% used</div>
    </div>
  );
}

// ── Chart gradient defs ────────────────────────────────────────────────────
const ChartGradients = () => (
  <defs>
    <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stopColor={C.allow}   stopOpacity={0.3} />
      <stop offset="100%" stopColor={C.allow}   stopOpacity={0} />
    </linearGradient>
    <linearGradient id="gw" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stopColor={C.approve} stopOpacity={0.3} />
      <stop offset="100%" stopColor={C.approve} stopOpacity={0} />
    </linearGradient>
    <linearGradient id="gd" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stopColor={C.deny}    stopOpacity={0.3} />
      <stop offset="100%" stopColor={C.deny}    stopOpacity={0} />
    </linearGradient>
  </defs>
);

const tooltipStyle = {
  contentStyle: {
    background: "var(--s0-card)", border: "1px solid rgba(148,163,184,0.12)",
    borderRadius: "10px", fontSize: "12px", color: "#3F3F46",
  },
  cursor: { stroke: "var(--s0-accent-ring)", strokeWidth: 1 },
};

// ── Main ───────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [chartWindow, setChartWindow] = useState<"24h" | "30d">("24h");

  // ── Queries ──────────────────────────────────────────────────────────────
  const since30d = useMemo(() => new Date(Date.now() - 30 * 86400e3).toISOString(), []);

  const { data: recentEvents = [] } = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => api.get<any[]>("/api/v1/audit/events?limit=100"),
  });

  const { data: events30d = [] } = useQuery({
    queryKey: ["audit", "events", "30d"],
    queryFn: () =>
      api.get<any[]>(`/api/v1/audit/events?limit=5000&since=${encodeURIComponent(since30d)}`),
  });

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<any[]>("/api/v1/agents"),
  });

  const { data: policies = [] } = useQuery({
    queryKey: ["policies"],
    queryFn: () => api.get<any[]>("/api/v1/policies"),
  });

  const { data: usage } = useQuery({
    queryKey: ["billing", "usage"],
    queryFn: () =>
      api.get<{
        decisions_used: number;
        decisions_included: number;
        period_start: string;
        period_end: string;
      }>("/api/v1/billing/usage").catch(() => null),
  });

  const { data: sub } = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: () =>
      api.get<{ plan: string; seats_included: number; seats_used?: number }>(
        "/api/v1/billing/subscription"
      ).catch(() => null),
  });

  // ── Derived stats ─────────────────────────────────────────────────────────
  const activeAgents     = agents.filter((a: any) => a.is_active).length;
  const isNew            = agents.length === 0;

  const decisions30d  = events30d.filter((e: any) => e.event_type === "policy.decision");
  const approvalsPending = decisions30d.filter((e: any) => e.outcome === "require_approval").length;
  const denials30d       = decisions30d.filter((e: any) => e.outcome === "deny").length;
  const total30d         = decisions30d.length;

  // ── 24h chart buckets ──────────────────────────────────────────────────
  const buckets24h = useMemo(() => {
    const hours: Record<string, any> = {};
    for (let i = 23; i >= 0; i--) {
      const h = new Date(Date.now() - i * 3600e3);
      const key = h.getHours().toString().padStart(2, "0") + "h";
      hours[key] = { label: key, allow: 0, deny: 0, require_approval: 0 };
    }
    for (const e of recentEvents) {
      if (e.event_type !== "policy.decision") continue;
      const k = new Date(e.ts).getHours().toString().padStart(2, "0") + "h";
      if (hours[k]) hours[k][e.outcome] = (hours[k][e.outcome] || 0) + 1;
    }
    return Object.values(hours);
  }, [recentEvents]);

  // ── 30d chart buckets ──────────────────────────────────────────────────
  const buckets30d = useMemo(() => {
    const days: Record<string, any> = {};
    for (let i = 29; i >= 0; i--) {
      const k = dayLabel(new Date(Date.now() - i * 86400e3));
      days[k] = { label: k, allow: 0, deny: 0, require_approval: 0 };
    }
    for (const e of events30d) {
      if (e.event_type !== "policy.decision") continue;
      const k = dayLabel(new Date(e.ts));
      if (days[k]) days[k][e.outcome] = (days[k][e.outcome] || 0) + 1;
    }
    return Object.values(days);
  }, [events30d]);

  // ── Top agents ─────────────────────────────────────────────────────────
  const topAgents = useMemo(() => {
    const counts: Record<string, { allow: number; deny: number; total: number }> = {};
    for (const e of events30d) {
      if (e.event_type !== "policy.decision") continue;
      const id = e.actor?.replace("agent:", "") ?? "unknown";
      if (!counts[id]) counts[id] = { allow: 0, deny: 0, total: 0 };
      counts[id].total++;
      if (e.outcome === "allow") counts[id].allow++;
      if (e.outcome === "deny")  counts[id].deny++;
    }
    return Object.entries(counts)
      .map(([id, c]) => {
        const agent = agents.find((a: any) => a.id === id || a.slug === id);
        return { id, name: agent?.name ?? id, ...c };
      })
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
  }, [events30d, agents]);

  // ── Agent decision report ──────────────────────────────────────────────
  const agentReport = useMemo(() => {
    const counts: Record<string, {
      allow: number; require_approval: number; deny: number; total: number;
    }> = {};
    for (const e of events30d) {
      if (e.event_type !== "policy.decision") continue;
      const actor: string = e.actor || "";
      if (!actor.startsWith("agent:")) continue;
      const id = actor.replace("agent:", "");
      if (!counts[id]) counts[id] = { allow: 0, require_approval: 0, deny: 0, total: 0 };
      counts[id].total++;
      if (e.outcome === "allow")            counts[id].allow++;
      if (e.outcome === "require_approval") counts[id].require_approval++;
      if (e.outcome === "deny")             counts[id].deny++;
    }
    return Object.entries(counts)
      .map(([id, c]) => {
        const agent = agents.find((a: any) => a.id === id);
        return {
          id,
          name: agent?.display_name ?? agent?.slug ?? id,
          ...c,
          autonomous_pct: c.total ? +(c.allow / c.total * 100).toFixed(1) : 0,
          approval_pct:   c.total ? +(c.require_approval / c.total * 100).toFixed(1) : 0,
        };
      })
      .sort((a, b) => b.total - a.total);
  }, [events30d, agents]);

  function downloadReportCSV() {
    const header = ["agent_id", "agent_name", "autonomous", "require_approval", "denied", "total", "autonomous_%", "approval_%"];
    const rows = agentReport.map(r => [
      r.id, r.name, r.allow, r.require_approval, r.deny, r.total, r.autonomous_pct, r.approval_pct,
    ]);
    const csv = [header, ...rows].map(row => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `kynara-agent-report-30d-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const chartData  = chartWindow === "24h" ? buckets24h : buckets30d;
  const chartXKey  = "label";
  const xInterval  = chartWindow === "24h" ? 3 : 6;

  const periodEnd = usage?.period_end
    ? new Date(usage.period_end).toLocaleDateString([], { month: "short", day: "numeric" })
    : "—";

  const stats = [
    {
      label: "Active agents", value: String(activeAgents),
      delta: activeAgents === 0 ? "Create your first agent" : `${activeAgents} running`,
      tone: "info" as Tone, icon: Bot, to: "/app/agents",
    },
    {
      label: "Decisions (30d)", value: fmtN(total30d),
      delta: total30d === 0 ? "No decisions yet" : `${total30d} evaluated`,
      tone: "ok" as Tone, icon: TrendingUp, to: "/app/audit",
    },
    {
      label: "Approvals pending", value: String(approvalsPending),
      delta: approvalsPending === 0 ? "None pending" : `${approvalsPending} awaiting review`,
      tone: "warn" as Tone, icon: AlertTriangle, to: "/app/approvals",
    },
    {
      label: "Denials (30d)", value: String(denials30d),
      delta: denials30d === 0 ? "No denials" : `${denials30d} blocked`,
      tone: "danger" as Tone, icon: XCircle, to: "/app/audit",
    },
  ];

  return (
    <div className="page-enter">
      <PageHeader
        title="Overview"
        subtitle="Agent activity, authorization decisions, and quota."
      />

      {/* ── Stat cards ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 px-6 pt-5 pb-4">
        {stats.map((s) => {
          const t = TONE[s.tone];
          return (
            <Link key={s.label} to={s.to}
              className="stat-card hover:border-accent-600/40 transition-colors group">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[11px] font-medium text-ink-400 mb-2">{s.label}</div>
                  <div className="text-xl font-bold text-ink-50 tabular-nums tracking-tight">
                    {s.value}
                  </div>
                  <div className={`text-xs font-medium mt-1.5 ${t.text}`}>{s.delta}</div>
                </div>
                <div className="size-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: t.bg, border: `1px solid ${t.border}` }}>
                  <s.icon className="size-4" style={{ color: t.iconColor }} />
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* ── Getting started (empty state) ─────────────────────────────────── */}
      {isNew && (
        <div className="mx-6 mb-4 rounded-xl p-4"
          style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)" }}>
          <div className="text-sm font-semibold text-ink-50 mb-3">Get started with Kynara</div>
          <div className="grid md:grid-cols-3 gap-3">
            {[
              { step: "1", icon: Bot,        title: "Register an agent",
                desc: "Give your AI agent an identity and supervision mode.",
                to: "/app/agents",      cta: "New agent" },
              { step: "2", icon: ShieldCheck, title: "Create a policy",
                desc: "Define what the agent can and cannot do per action and resource.",
                to: "/app/policies/new", cta: "New policy" },
              { step: "3", icon: FileText,    title: "Review audit logs",
                desc: "Every decision is logged with actor, outcome, and context.",
                to: "/app/audit",       cta: "View audit" },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.step} className="flex gap-3">
                  <div className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mt-0.5"
                    style={{ background: "var(--s0-accent-ring)", color: "var(--s0-accent-text)" }}>
                    {item.step}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-ink-50 flex items-center gap-2 mb-0.5">
                      <Icon className="size-3.5" style={{ color: "var(--s0-accent-text)" }} /> {item.title}
                    </div>
                    <p className="text-xs text-ink-400 mb-2">{item.desc}</p>
                    <Link to={item.to}
                      className="inline-flex items-center gap-1 text-xs font-medium"
                      style={{ color: "var(--s0-accent-text)" }}>
                      {item.cta} <ArrowRight className="size-3" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Chart + Quota row ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 px-6 pb-4">

        {/* Area chart with 24h / 30d toggle */}
        <div className="lg:col-span-2 card p-4">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-ink-50">Decision volume</div>
              <div className="text-xs text-ink-300 mt-0.5">Allow · require approval · deny</div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                {[["allow", C.allow], ["approval", C.approve], ["deny", C.deny]].map(([l, col]) => (
                  <span key={l} className="flex items-center gap-1 text-[10px] font-medium text-ink-300">
                    <span className="size-2 rounded-full inline-block" style={{ background: col as string }} />{l}
                  </span>
                ))}
              </div>
              {/* Time window toggle */}
              <div className="flex rounded-md overflow-hidden border border-ink-700/60 text-[10px] font-semibold">
                {(["24h", "30d"] as const).map((w) => (
                  <button
                    key={w}
                    onClick={() => setChartWindow(w)}
                    className="px-2.5 py-1 transition-colors"
                    style={{
                      background: chartWindow === w ? "var(--s0-accent-ring)" : "transparent",
                      color: chartWindow === w ? "var(--s0-accent-text)" : "#475569",
                    }}
                  >
                    {w}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <ChartGradients />
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" vertical={false} />
                <XAxis dataKey={chartXKey} stroke="rgba(0,0,0,0)"
                  tick={{ fill: "#475569", fontSize: 9 }} tickLine={false} axisLine={false}
                  interval={xInterval} />
                <YAxis stroke="rgba(0,0,0,0)"
                  tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip {...tooltipStyle} />
                <Area type="monotone" dataKey="allow"            stroke={C.allow}   strokeWidth={1.8} fill="url(#ga)" />
                <Area type="monotone" dataKey="require_approval" stroke={C.approve} strokeWidth={1.8} fill="url(#gw)" />
                <Area type="monotone" dataKey="deny"             stroke={C.deny}    strokeWidth={1.8} fill="url(#gd)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Plan quota card */}
        <div className="card p-5 flex flex-col gap-5">
          <div className="flex items-center gap-2">
            <Zap className="size-4" style={{ color: C.quota }} />
            <span className="text-sm font-semibold text-ink-50">Plan quota</span>
            {sub?.plan && (
              <span className="ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full"
                style={{ background: "var(--s0-accent-ring)", color: "var(--s0-accent-text)" }}>
                {sub.plan.toUpperCase()}
              </span>
            )}
          </div>

          {usage ? (
            <QuotaMeter
              label="Decisions this period"
              used={usage.decisions_used ?? 0}
              total={usage.decisions_included ?? 1}
              color={C.quota}
            />
          ) : (
            <div className="text-xs text-ink-500">No billing data</div>
          )}

          {sub && sub.seats_used !== undefined && (
            <QuotaMeter
              label="Seats occupied"
              used={sub.seats_used ?? 0}
              total={sub.seats_included ?? 1}
              color={C.accent}
            />
          )}

          <div className="mt-auto pt-3 border-t border-ink-700/60 text-xs text-ink-400 flex items-center justify-between">
            <span>Resets <span className="text-ink-200">{periodEnd}</span></span>
            <Link to="/app/billing" className="text-[10px] font-medium"
              style={{ color: "var(--s0-accent-text)" }}>
              Billing →
            </Link>
          </div>
        </div>
      </div>

      {/* ── Agent decisions report ───────────────────────────────────────── */}
      <div className="px-6 pb-4">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart2 className="size-4 text-ink-300" />
              <span className="text-sm font-semibold text-ink-50">Agent decisions report</span>
              <span className="text-xs text-ink-500 ml-1">autonomous vs human approval · 30d</span>
            </div>
            {agentReport.length > 0 && (
              <button
                onClick={downloadReportCSV}
                className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors"
                style={{ background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)", border: "1px solid var(--s0-accent-ring)" }}
              >
                <Download className="size-3" /> Export CSV
              </button>
            )}
          </div>

          {agentReport.length === 0 ? (
            <div className="py-6 text-center">
              <p className="text-xs text-ink-400">No agent decision data for the last 30 days.</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-ink-700/60">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-ink-700/60">
                    <th className="text-left px-3 py-2.5 text-ink-400 font-medium">Agent</th>
                    <th className="text-right px-3 py-2.5 text-ink-400 font-medium">
                      <span style={{ color: C.allow }}>Autonomous</span>
                    </th>
                    <th className="text-right px-3 py-2.5 text-ink-400 font-medium">
                      <span style={{ color: C.approve }}>Approval</span>
                    </th>
                    <th className="text-right px-3 py-2.5 text-ink-400 font-medium">
                      <span style={{ color: C.deny }}>Denied</span>
                    </th>
                    <th className="text-right px-3 py-2.5 text-ink-400 font-medium">Total</th>
                    <th className="text-right px-3 py-2.5 text-ink-400 font-medium w-40">Autonomy rate</th>
                  </tr>
                </thead>
                <tbody>
                  {agentReport.map((a, i) => (
                    <tr key={a.id} className={i % 2 === 0 ? "" : "bg-ink-800/30"}>
                      <td className="px-3 py-2 font-medium text-ink-100 truncate max-w-[140px]">{a.name}</td>
                      <td className="px-3 py-2 tabular-nums text-right" style={{ color: C.allow }}>
                        {fmtN(a.allow)}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-right" style={{ color: C.approve }}>
                        {fmtN(a.require_approval)}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-right" style={{ color: C.deny }}>
                        {fmtN(a.deny)}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-right text-ink-300">
                        {fmtN(a.total)}
                      </td>
                      <td className="px-3 py-2">
                        {/* Stacked bar: autonomous (green) + approval (orange) + deny (red) */}
                        <div className="flex items-center gap-1.5">
                          <div className="flex-1 h-2 rounded-full overflow-hidden flex bg-ink-700">
                            <div style={{ width: `${a.autonomous_pct}%`, background: C.allow }}   className="h-full" />
                            <div style={{ width: `${a.approval_pct}%`,   background: C.approve }} className="h-full" />
                            <div style={{
                              width: `${a.total ? +(a.deny / a.total * 100).toFixed(1) : 0}%`,
                              background: C.deny
                            }} className="h-full" />
                          </div>
                          <span className="tabular-nums text-[10px] text-ink-300 w-9 text-right">
                            {a.autonomous_pct}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Top agents + Live feed row ────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 px-6 pb-8">

        {/* Top agents */}
        <div className="lg:col-span-2 card p-4">
          <div className="flex items-center gap-2 mb-4">
            <Bot className="size-4 text-ink-300" />
            <span className="text-sm font-semibold text-ink-50">Top agents</span>
            <span className="text-xs text-ink-500 ml-1">by decision volume · 30d</span>
          </div>

          {topAgents.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-xs text-ink-400 mb-3">No agent activity yet.</p>
              <Link to="/app/agents"
                className="inline-flex items-center gap-1.5 text-xs font-medium rounded-lg px-3 py-1.5"
                style={{ background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)" }}>
                <Plus className="size-3" /> Create your first agent
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topAgents.slice(0, 6)}
                    layout="vertical"
                    margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" horizontal={false} />
                    <XAxis type="number" stroke="rgba(0,0,0,0)"
                      tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="name" width={80}
                      stroke="rgba(0,0,0,0)" tick={{ fill: "#94A3B8", fontSize: 10 }}
                      tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: "var(--s0-card)", border: "1px solid rgba(148,163,184,0.12)",
                        borderRadius: "10px", fontSize: "12px", color: "#3F3F46" }}
                      cursor={{ fill: "var(--s0-accent-subtle)" }}
                    />
                    <Bar dataKey="allow" stackId="a" fill={C.allow} />
                    <Bar dataKey="deny"  stackId="a" fill={C.deny}  radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-hidden rounded-lg border border-ink-700/60">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-ink-700/60">
                      <th className="text-left px-3 py-2 text-ink-400 font-medium">Agent</th>
                      <th className="text-right px-3 py-2 text-ink-400 font-medium">Total</th>
                      <th className="text-right px-3 py-2 text-ink-400 font-medium">Allow%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topAgents.map((a, i) => (
                      <tr key={a.id} className={i % 2 === 0 ? "" : "bg-ink-800/30"}>
                        <td className="px-3 py-2 text-ink-200 font-medium truncate max-w-[100px]">
                          {a.name}
                        </td>
                        <td className="px-3 py-2 text-ink-300 tabular-nums text-right">
                          {fmtN(a.total)}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold"
                            style={{
                              background: a.total ? `${C.allow}18` : "transparent",
                              color: a.total ? C.allow : "#475569",
                            }}>
                            {a.total ? Math.round((a.allow / a.total) * 100) : 0}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Live activity feed */}
        <div className="card p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold text-ink-50">Recent activity</div>
            <span className="pill pill-teal flex items-center gap-1">
              <span className="size-1.5 rounded-full"
                style={{ background: C.teal, boxShadow: `0 0 5px ${C.teal}` }} />
              live
            </span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-1 -mx-1 px-1">
            {recentEvents.slice(0, 20).map((e: any) => {
              const col = e.outcome === "allow" ? C.allow
                : e.outcome === "deny" ? C.deny : C.approve;
              return (
                <div key={e.id}
                  className="flex items-start gap-2.5 py-1.5 text-xs rounded-md px-1 hover:bg-ink-700/40 transition-colors">
                  <div className="mt-1.5 size-1.5 rounded-full shrink-0" style={{ background: col }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-ink-100 truncate font-medium">{e.event_type}</div>
                    <div className="text-ink-400 font-mono truncate text-[10px] mt-0.5">
                      {e.actor} → {e.resource_type || "–"}
                    </div>
                  </div>
                  <div className="text-ink-500 text-[10px] tabular-nums shrink-0">
                    {new Date(e.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              );
            })}
            {!recentEvents.length && (
              <div className="py-10 text-center">
                <p className="text-xs text-ink-400 mb-3">No activity yet.</p>
                <Link to="/app/agents"
                  className="inline-flex items-center gap-1.5 text-xs font-medium rounded-lg px-3 py-1.5"
                  style={{ background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)" }}>
                  <Plus className="size-3" /> Create your first agent
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
