import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Bot, CheckCircle2, XCircle, AlertTriangle, TrendingUp,
  ArrowRight, ShieldCheck, FileText, Plus,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── Design tokens ──────────────────────────────────────────────────────────
const C = {
  allow:   "#10B981",
  approve: "#F59E0B",
  deny:    "#F43F5E",
  accent:  "#6366F1",
  teal:    "#2DD4BF",
};

type Tone = "ok" | "warn" | "danger" | "info";
const TONE: Record<Tone, { text: string; iconColor: string; bg: string; border: string }> = {
  ok:     { text: "text-ok-400",     iconColor: C.allow,   bg: "rgba(16,185,129,0.09)",  border: "rgba(4,120,87,0.25)" },
  warn:   { text: "text-warn-400",   iconColor: C.approve, bg: "rgba(245,158,11,0.09)",  border: "rgba(180,83,9,0.25)" },
  danger: { text: "text-danger-400", iconColor: C.deny,    bg: "rgba(244,63,94,0.09)",   border: "rgba(190,18,60,0.25)" },
  info:   { text: "text-accent-400", iconColor: C.accent,  bg: "rgba(99,102,241,0.09)",  border: "rgba(67,56,202,0.25)" },
};

export default function DashboardPage() {
  const { data: events } = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => api.get<any[]>("/api/v1/audit/events?limit=100"),
  });

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<any[]>("/api/v1/agents"),
  });

  const { data: policies = [] } = useQuery({
    queryKey: ["policies"],
    queryFn: () => api.get<any[]>("/api/v1/policies"),
  });

  const bucketed = bucketDecisions(events || []);
  const activeAgents = agents.filter((a: any) => a.is_active).length;
  const decisions7d = (events || []).filter((e: any) => {
    const ts = new Date(e.ts).getTime();
    return ts > Date.now() - 7 * 86400e3 && e.event_type === "policy.decision";
  });
  const approvalsPending = decisions7d.filter((e: any) => e.outcome === "require_approval").length;
  const denials7d       = decisions7d.filter((e: any) => e.outcome === "deny").length;
  const totalDecisions  = decisions7d.length;
  const isNew = agents.length === 0;

  const fmt = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

  const stats = [
    {
      label: "Active agents", value: String(activeAgents),
      delta: activeAgents === 0 ? "Create your first agent" : `${activeAgents} running`,
      tone: "info" as Tone, icon: Bot, to: "/app/agents",
    },
    {
      label: "Decisions (7d)", value: fmt(totalDecisions),
      delta: totalDecisions === 0 ? "No decisions yet" : `${totalDecisions} evaluated`,
      tone: "ok" as Tone, icon: TrendingUp, to: "/app/audit",
    },
    {
      label: "Approvals pending", value: String(approvalsPending),
      delta: approvalsPending === 0 ? "None pending" : `${approvalsPending} awaiting review`,
      tone: "warn" as Tone, icon: AlertTriangle, to: "/app/approvals",
    },
    {
      label: "Denials (7d)", value: String(denials7d),
      delta: denials7d === 0 ? "No denials" : `${denials7d} blocked`,
      tone: "danger" as Tone, icon: XCircle, to: "/app/audit",
    },
  ];

  return (
    <div className="page-enter">
      <PageHeader
        title="Overview"
        subtitle="Agent activity, authorization decisions, and pending approvals."
      />

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 px-6 pt-5 pb-4">
        {stats.map((s) => {
          const t = TONE[s.tone];
          return (
            <Link key={s.label} to={s.to} className="stat-card hover:border-accent-600/40 transition-colors group">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[11px] font-medium text-ink-400 mb-2">{s.label}</div>
                  <div className="text-xl font-bold text-white tabular-nums tracking-tight">
                    {s.value}
                  </div>
                  <div className={`text-xs font-medium mt-1.5 ${t.text}`}>{s.delta}</div>
                </div>
                <div
                  className="size-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: t.bg, border: `1px solid ${t.border}` }}
                >
                  <s.icon className="size-4" style={{ color: t.iconColor }} />
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* ── Getting started panel (shown only for empty orgs) ── */}
      {isNew && (
        <div className="mx-6 mb-4 rounded-xl p-4"
          style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)" }}>
          <div className="text-sm font-semibold text-white mb-3">Get started with Kynara</div>
          <div className="grid md:grid-cols-3 gap-3">
            {[
              {
                step: "1", icon: Bot, title: "Register an agent",
                desc: "Give your AI agent an identity and supervision mode.",
                to: "/app/agents", cta: "New agent",
              },
              {
                step: "2", icon: ShieldCheck, title: "Create a policy",
                desc: "Define what the agent can and cannot do per action and resource.",
                to: "/app/policies/new", cta: "New policy",
              },
              {
                step: "3", icon: FileText, title: "Review audit logs",
                desc: "Every decision is logged with actor, outcome, and context.",
                to: "/app/audit", cta: "View audit",
              },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.step} className="flex gap-3">
                  <div className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mt-0.5"
                    style={{ background: "rgba(99,102,241,0.2)", color: "#818CF8" }}>
                    {item.step}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white flex items-center gap-2 mb-0.5">
                      <Icon className="size-3.5" style={{ color: "#818CF8" }} /> {item.title}
                    </div>
                    <p className="text-xs text-ink-400 mb-2">{item.desc}</p>
                    <Link to={item.to}
                      className="inline-flex items-center gap-1 text-xs font-medium"
                      style={{ color: "#818CF8" }}>
                      {item.cta} <ArrowRight className="size-3" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 px-6 pb-6">
        {/* ── Area chart ── */}
        <div className="lg:col-span-2 card p-4">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-white">Decision volume</div>
              <div className="text-xs text-ink-300 mt-0.5">Allow · require approval · deny · last 24h</div>
            </div>
            <div className="flex items-center gap-2">
              <span className="pill pill-ok"><CheckCircle2 className="size-3" />allow</span>
              <span className="pill pill-warn"><AlertTriangle className="size-3" />approval</span>
              <span className="pill pill-danger"><XCircle className="size-3" />deny</span>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={bucketed} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <defs>
                  <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor={C.allow}   stopOpacity={0.35} />
                    <stop offset="100%" stopColor={C.allow}   stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gw" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor={C.approve} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={C.approve} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gd" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor={C.deny}    stopOpacity={0.35} />
                    <stop offset="100%" stopColor={C.deny}    stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" vertical={false} />
                <XAxis dataKey="hour" stroke="rgba(148,163,184,0)" tick={{ fill: "#475569", fontSize: 10 }}
                  tickLine={false} axisLine={false} />
                <YAxis stroke="rgba(148,163,184,0)" tick={{ fill: "#475569", fontSize: 10 }}
                  tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)",
                    borderRadius: "10px", fontSize: "12px", color: "#CBD5E1" }}
                  cursor={{ stroke: "rgba(99,102,241,0.2)", strokeWidth: 1 }}
                />
                <Area type="monotone" dataKey="allow"            stroke={C.allow}   strokeWidth={1.8} fill="url(#ga)" />
                <Area type="monotone" dataKey="require_approval" stroke={C.approve} strokeWidth={1.8} fill="url(#gw)" />
                <Area type="monotone" dataKey="deny"             stroke={C.deny}    strokeWidth={1.8} fill="url(#gd)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Activity feed ── */}
        <div className="card p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold text-white">Recent activity</div>
            <span className="pill pill-teal flex items-center gap-1">
              <span className="size-1.5 rounded-full" style={{ background: C.teal, boxShadow: `0 0 5px ${C.teal}` }} />
              live
            </span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-1 -mx-1 px-1">
            {(events || []).slice(0, 20).map((e) => {
              const col = e.outcome === "allow" ? C.allow : e.outcome === "deny" ? C.deny : C.approve;
              return (
                <div key={e.id} className="flex items-start gap-2.5 py-1.5 text-xs group rounded-md px-1 hover:bg-ink-700/40 transition-colors">
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
            {!events?.length && (
              <div className="py-10 text-center">
                <p className="text-xs text-ink-400 mb-3">No activity yet.</p>
                <Link to="/app/agents"
                  className="inline-flex items-center gap-1.5 text-xs font-medium rounded-lg px-3 py-1.5"
                  style={{ background: "rgba(99,102,241,0.12)", color: "#818CF8" }}>
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

function bucketDecisions(evts: any[]) {
  const hours: Record<string, any> = {};
  for (let i = 23; i >= 0; i--) {
    const h = new Date(Date.now() - i * 3600e3);
    const key = h.getHours().toString().padStart(2, "0") + "h";
    hours[key] = { hour: key, allow: 0, deny: 0, require_approval: 0 };
  }
  for (const e of evts) {
    if (e.event_type !== "policy.decision") continue;
    const h = new Date(e.ts).getHours().toString().padStart(2, "0") + "h";
    if (hours[h]) hours[h][e.outcome] = (hours[h][e.outcome] || 0) + 1;
  }
  return Object.values(hours);
}
