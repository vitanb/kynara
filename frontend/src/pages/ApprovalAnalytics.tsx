import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2, TrendingUp, Clock, CheckCircle2, XCircle, Timer } from "lucide-react";
import { useState } from "react";

interface Analytics {
  total: number; approved: number; rejected: number;
  expired: number; pending: number; approval_rate: number;
  avg_resolution_minutes: number | null;
  top_agents: { agent: string; count: number }[];
  top_actions: { action: string; count: number }[];
  daily: { date: string; approved: number; rejected: number; pending: number; expired: number }[];
  days: number;
}

function StatCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string | number; color: string }) {
  return (
    <div className="rounded-xl p-5" style={{ background: "var(--s0-surface,#FAFAF9)", border: "1px solid rgba(148,163,184,.1)" }}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4" style={{ color }} />
        <span className="text-xs text-ink-400 font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-2xl font-bold text-ink-50">{value}</div>
    </div>
  );
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-xs text-ink-400 w-40 truncate font-mono">{label}</span>
      <div className="flex-1 h-2 rounded-full" style={{ background: "rgba(148,163,184,.08)" }}>
        <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs text-ink-400 w-6 text-right">{value}</span>
    </div>
  );
}

function MiniChart({ daily }: { daily: Analytics["daily"] }) {
  const last14 = daily.slice(-14);
  const maxVal = Math.max(1, ...last14.map(d => d.approved + d.rejected + d.expired));
  return (
    <div className="flex items-end gap-1 h-20 mt-2">
      {last14.map((d) => {
        const total = d.approved + d.rejected + d.expired + d.pending;
        const h = Math.max(2, Math.round((total / maxVal) * 80));
        return (
          <div key={d.date} className="flex-1 relative group cursor-default">
            <div className="absolute bottom-0 left-0 right-0 rounded-sm transition-opacity"
              style={{ height: `${h}px`, background: d.approved > 0 ? "rgba(16,185,129,.6)" : "rgba(148,163,184,.2)" }} />
            <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block z-10
              text-xs text-ink-50 rounded px-1.5 py-0.5 whitespace-nowrap"
              style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,.15)" }}>
              {d.date.slice(5)}: {total}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function ApprovalAnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery<Analytics>({
    queryKey: ["approval-analytics", days],
    queryFn: () => api.get<Analytics>(`/api/v1/approvals/analytics?days=${days}`),
    staleTime: 60_000,
  });

  const card = "rounded-xl p-5";
  const cardStyle = { background: "var(--s0-surface,#FAFAF9)", border: "1px solid rgba(148,163,184,.1)" };
  const sectionTag = "text-xs font-bold uppercase tracking-widest text-indigo-400 mb-3";

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-ink-50">Approval Analytics</h1>
          <p className="text-sm text-ink-400 mt-0.5">Resolution times, rates, and trends</p>
        </div>
        <select value={days} onChange={e => setDays(Number(e.target.value))}
          className="text-sm rounded-lg px-3 py-2 text-ink-100 outline-none"
          style={{ background: "rgba(148,163,184,.06)", border: "1px solid rgba(148,163,184,.12)" }}>
          {[7, 14, 30, 90].map(d => <option key={d} value={d}>Last {d} days</option>)}
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-indigo-400" /></div>
      ) : data ? (
        <div className="space-y-6">
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard icon={TrendingUp} label="Total" value={data.total} color="var(--s0-accent-text)" />
            <StatCard icon={CheckCircle2} label="Approved" value={data.approved} color="#34D399" />
            <StatCard icon={XCircle} label="Rejected" value={data.rejected} color="#F43F5E" />
            <StatCard icon={Timer} label="Expired" value={data.expired} color="#F59E0B" />
            <StatCard icon={Clock} label="Avg. resolve" value={data.avg_resolution_minutes != null ? `${data.avg_resolution_minutes}m` : "—"} color="#38BDF8" />
          </div>

          {/* Rate + chart */}
          <div className="grid grid-cols-2 gap-4">
            <div className={card} style={cardStyle}>
              <div className={sectionTag}>Approval rate</div>
              <div className="text-3xl font-bold mb-1" style={{ color: data.approval_rate >= 70 ? "#34D399" : "#F59E0B" }}>
                {data.approval_rate}%
              </div>
              <div className="text-xs text-ink-400">{data.approved} approved / {data.approved + data.rejected} resolved</div>
              <div className="mt-3 h-2 rounded-full" style={{ background: "rgba(148,163,184,.08)" }}>
                <div className="h-2 rounded-full" style={{ width: `${data.approval_rate}%`, background: "#34D399" }} />
              </div>
            </div>
            <div className={card} style={cardStyle}>
              <div className={sectionTag}>Daily volume (last {Math.min(days,14)} days)</div>
              <MiniChart daily={data.daily} />
              <div className="flex gap-4 mt-2 text-xs text-ink-400">
                <span><span className="inline-block w-2 h-2 rounded-sm mr-1" style={{ background: "rgba(16,185,129,.6)" }} />Approved</span>
                <span><span className="inline-block w-2 h-2 rounded-sm mr-1" style={{ background: "rgba(148,163,184,.2)" }} />Other</span>
              </div>
            </div>
          </div>

          {/* Top agents + actions */}
          <div className="grid grid-cols-2 gap-4">
            <div className={card} style={cardStyle}>
              <div className={sectionTag}>Top agents by approvals</div>
              {data.top_agents.length === 0 ? <p className="text-sm text-ink-400">No data</p> :
                data.top_agents.map(a => <Bar key={a.agent} label={a.agent} value={a.count} max={data.top_agents[0]?.count || 1} color="var(--s0-accent-text)" />)
              }
            </div>
            <div className={card} style={cardStyle}>
              <div className={sectionTag}>Top actions</div>
              {data.top_actions.length === 0 ? <p className="text-sm text-ink-400">No data</p> :
                data.top_actions.map(a => <Bar key={a.action} label={a.action} value={a.count} max={data.top_actions[0]?.count || 1} color="#2DD4BF" />)
              }
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
