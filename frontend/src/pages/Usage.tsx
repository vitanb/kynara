/**
 * Usage dashboard — quota burn, 30-day decision trend, top agents.
 * Data sources: GET /api/v1/billing/usage, GET /api/v1/audit/events,
 *               GET /api/v1/agents
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, BarChart, Bar, CartesianGrid,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { TrendingUp, Bot, CheckCircle2, XCircle, AlertTriangle, Zap } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── palette ────────────────────────────────────────────────────────────────
const C = {
  allow:   "#10B981",
  deny:    "#F43F5E",
  approve: "#F59E0B",
  accent:  "#6366F1",
  quota:   "#2DD4BF",
};

// ── helpers ────────────────────────────────────────────────────────────────
function pct(used: number, total: number) {
  if (!total) return 0;
  return Math.min(100, Math.round((used / total) * 100));
}

function fmtN(n: number) {
  return n >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
    ? `${(n / 1_000).toFixed(1)}k`
    : String(n);
}

function dayLabel(d: Date) {
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// ── QuotaMeter ─────────────────────────────────────────────────────────────
function QuotaMeter({
  used, total, label, color,
}: { used: number; total: number; label: string; color: string }) {
  const p = pct(used, total);
  const tone = p >= 90 ? C.deny : p >= 70 ? C.approve : color;
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5 text-xs">
        <span className="text-ink-300 font-medium">{label}</span>
        <span className="text-ink-200 tabular-nums font-semibold">
          {fmtN(used)}
          <span className="text-ink-500 font-normal"> / {fmtN(total)}</span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-ink-700 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${p}%`, background: tone }}
        />
      </div>
      <div className="mt-1 text-[10px] text-ink-500 tabular-nums">{p}% used</div>
    </div>
  );
}

// ── StatCard ───────────────────────────────────────────────────────────────
function StatCard({
  label, value, sub, icon: Icon, color,
}: { label: string; value: string; sub: string; icon: any; color: string }) {
  return (
    <div className="card p-4 flex items-start gap-3">
      <div
        className="size-9 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}
      >
        <Icon className="size-4" style={{ color }} />
      </div>
      <div>
        <div className="text-[11px] font-medium text-ink-400 mb-1">{label}</div>
        <div className="text-xl font-bold text-white tabular-nums tracking-tight">{value}</div>
        <div className="text-xs text-ink-400 mt-1">{sub}</div>
      </div>
    </div>
  );
}

// ── main ───────────────────────────────────────────────────────────────────
export default function UsagePage() {
  // Billing quota
  const { data: usage } = useQuery({
    queryKey: ["billing", "usage"],
    queryFn: () =>
      api.get<{
        decisions_used: number;
        decisions_included: number;
        period_start: string;
        period_end: string;
      }>("/api/v1/billing/usage"),
  });

  // Subscription (for seat quota)
  const { data: sub } = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: () =>
      api.get<{
        plan: string;
        seats_included: number;
        seats_used?: number;
      }>("/api/v1/billing/subscription").catch(() => null),
  });

  // 30 days of audit events for trend + top-agent breakdown
  const since30d = useMemo(() => {
    const d = new Date(Date.now() - 30 * 86400e3);
    return d.toISOString();
  }, []);

  const { data: events = [] } = useQuery({
    queryKey: ["audit", "events", "30d"],
    queryFn: () =>
      api.get<any[]>(
        `/api/v1/audit/events?limit=5000&since=${encodeURIComponent(since30d)}`
      ),
  });

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<any[]>("/api/v1/agents"),
  });

  // ── compute 30-day trend bucketed by day ──────────────────────────────
  const dailyTrend = useMemo(() => {
    const days: Record<string, { day: string; allow: number; deny: number; require_approval: number }> = {};
    for (let i = 29; i >= 0; i--) {
      const d = new Date(Date.now() - i * 86400e3);
      const k = dayLabel(d);
      days[k] = { day: k, allow: 0, deny: 0, require_approval: 0 };
    }
    for (const e of events) {
      if (e.event_type !== "policy.decision") continue;
      const k = dayLabel(new Date(e.ts));
      if (days[k]) {
        const out = e.outcome as "allow" | "deny" | "require_approval";
        if (out in days[k]) days[k][out]++;
      }
    }
    return Object.values(days);
  }, [events]);

  // ── top agents by decision count ──────────────────────────────────────
  const topAgents = useMemo(() => {
    const counts: Record<string, { allow: number; deny: number; total: number }> = {};
    for (const e of events) {
      if (e.event_type !== "policy.decision") continue;
      const id = e.actor?.replace("agent:", "") ?? "unknown";
      if (!counts[id]) counts[id] = { allow: 0, deny: 0, total: 0 };
      counts[id].total++;
      if (e.outcome === "allow") counts[id].allow++;
      if (e.outcome === "deny") counts[id].deny++;
    }
    return Object.entries(counts)
      .map(([id, c]) => {
        const agent = agents.find((a: any) => a.id === id || a.slug === id);
        return { id, name: agent?.name ?? id, ...c };
      })
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
  }, [events, agents]);

  // ── summary stats ─────────────────────────────────────────────────────
  const decisions30d = events.filter((e: any) => e.event_type === "policy.decision").length;
  const allows30d    = events.filter((e: any) => e.outcome === "allow").length;
  const denials30d   = events.filter((e: any) => e.outcome === "deny").length;
  const approvals30d = events.filter((e: any) => e.outcome === "require_approval").length;

  const periodStart = usage?.period_start
    ? new Date(usage.period_start).toLocaleDateString([], { month: "short", day: "numeric" })
    : "—";
  const periodEnd = usage?.period_end
    ? new Date(usage.period_end).toLocaleDateString([], { month: "short", day: "numeric" })
    : "—";

  return (
    <div className="page-enter">
      <PageHeader
        title="Usage"
        subtitle={`Quota burn and decision activity. Billing period: ${periodStart} – ${periodEnd}`}
      />

      {/* ── Stat strip ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 px-6 pt-5 pb-4">
        <StatCard label="Decisions (30d)" value={fmtN(decisions30d)}
          sub="policy checks evaluated" icon={TrendingUp} color={C.accent} />
        <StatCard label="Allowed (30d)"   value={fmtN(allows30d)}
          sub="passed all policies"       icon={CheckCircle2} color={C.allow} />
        <StatCard label="Denied (30d)"    value={fmtN(denials30d)}
          sub="blocked by policy"         icon={XCircle}      color={C.deny} />
        <StatCard label="Approvals (30d)" value={fmtN(approvals30d)}
          sub="routed to human review"    icon={AlertTriangle} color={C.approve} />
      </div>

      {/* ── Quota meters + trend chart ──────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 px-6 pb-4">

        {/* quota card */}
        <div className="card p-5 flex flex-col gap-5">
          <div className="flex items-center gap-2">
            <Zap className="size-4" style={{ color: C.quota }} />
            <span className="text-sm font-semibold text-white">Plan quota</span>
            {sub?.plan && (
              <span className="ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full"
                style={{ background: "rgba(99,102,241,0.15)", color: "#818CF8" }}>
                {sub.plan.toUpperCase()}
              </span>
            )}
          </div>

          <QuotaMeter
            label="Decisions this period"
            used={usage?.decisions_used ?? 0}
            total={usage?.decisions_included ?? 1}
            color={C.quota}
          />

          {sub && (sub.seats_used !== undefined) && (
            <QuotaMeter
              label="Seats occupied"
              used={sub.seats_used ?? 0}
              total={sub.seats_included ?? 1}
              color={C.accent}
            />
          )}

          <div className="mt-auto pt-2 border-t border-ink-700/60 text-xs text-ink-400">
            Period resets on <span className="text-ink-200">{periodEnd}</span>
          </div>
        </div>

        {/* 30-day trend */}
        <div className="lg:col-span-2 card p-4">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-white">Decision trend</div>
              <div className="text-xs text-ink-300 mt-0.5">Allow · require approval · deny · last 30 days</div>
            </div>
            <div className="flex items-center gap-2">
              {[["allow", C.allow], ["approval", C.approve], ["deny", C.deny]].map(([l, c]) => (
                <span key={l} className="flex items-center gap-1 text-[10px] font-medium text-ink-300">
                  <span className="size-2 rounded-full inline-block" style={{ background: c }} />
                  {l}
                </span>
              ))}
            </div>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyTrend} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <defs>
                  {[["ga", C.allow], ["gw", C.approve], ["gd", C.deny]].map(([id, col]) => (
                    <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor={col} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={col} stopOpacity={0}   />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" vertical={false} />
                <XAxis dataKey="day" stroke="rgba(0,0,0,0)" tick={{ fill: "#475569", fontSize: 9 }}
                  tickLine={false} axisLine={false} interval={6} />
                <YAxis stroke="rgba(0,0,0,0)" tick={{ fill: "#475569", fontSize: 10 }}
                  tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)",
                    borderRadius: "10px", fontSize: "12px", color: "#CBD5E1" }}
                  cursor={{ stroke: "rgba(99,102,241,0.15)", strokeWidth: 1 }}
                />
                <Area type="monotone" dataKey="allow"            stroke={C.allow}   strokeWidth={1.8} fill="url(#ga)" />
                <Area type="monotone" dataKey="require_approval" stroke={C.approve} strokeWidth={1.8} fill="url(#gw)" />
                <Area type="monotone" dataKey="deny"             stroke={C.deny}    strokeWidth={1.8} fill="url(#gd)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Top agents ─────────────────────────────────────────────────────── */}
      <div className="px-6 pb-8">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-4">
            <Bot className="size-4 text-ink-300" />
            <span className="text-sm font-semibold text-white">Top agents by decision volume</span>
            <span className="text-xs text-ink-500 ml-1">last 30 days</span>
          </div>

          {topAgents.length === 0 ? (
            <p className="text-xs text-ink-400 py-6 text-center">No decision data yet.</p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* bar chart */}
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topAgents.slice(0, 6)}
                    layout="vertical"
                    margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" horizontal={false} />
                    <XAxis type="number" stroke="rgba(0,0,0,0)"
                      tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="name" width={90}
                      stroke="rgba(0,0,0,0)" tick={{ fill: "#94A3B8", fontSize: 10 }}
                      tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)",
                        borderRadius: "10px", fontSize: "12px", color: "#CBD5E1" }}
                      cursor={{ fill: "rgba(99,102,241,0.06)" }}
                    />
                    <Bar dataKey="allow" stackId="a" fill={C.allow}   radius={[0, 0, 0, 0]} />
                    <Bar dataKey="deny"  stackId="a" fill={C.deny}    radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* table */}
              <div className="overflow-hidden rounded-lg border border-ink-700/60">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-ink-700/60">
                      <th className="text-left px-3 py-2 text-ink-400 font-medium">Agent</th>
                      <th className="text-right px-3 py-2 text-ink-400 font-medium">Total</th>
                      <th className="text-right px-3 py-2 text-ink-400 font-medium">Allow</th>
                      <th className="text-right px-3 py-2 text-ink-400 font-medium">Deny</th>
                      <th className="text-right px-3 py-2 text-ink-400 font-medium">Allow %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topAgents.map((a, i) => (
                      <tr key={a.id} className={i % 2 === 0 ? "" : "bg-ink-800/30"}>
                        <td className="px-3 py-2 text-ink-200 font-medium truncate max-w-[120px]">{a.name}</td>
                        <td className="px-3 py-2 text-ink-300 tabular-nums text-right">{fmtN(a.total)}</td>
                        <td className="px-3 py-2 tabular-nums text-right" style={{ color: C.allow }}>{fmtN(a.allow)}</td>
                        <td className="px-3 py-2 tabular-nums text-right" style={{ color: C.deny }}>{fmtN(a.deny)}</td>
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
      </div>
    </div>
  );
}
