import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert, Plus, Trash2, ToggleLeft, ToggleRight,
  AlertTriangle, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp,
  ExternalLink, Copy, Check, Zap, Filter,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────────────────
type Provider = "arize" | "langfuse" | "whylabs" | "fiddler" | "custom";
type Action = "alert_only" | "suspend_agent" | "revoke_jit_grants" | "deny_all_policy" | "reduce_to_readonly";

interface GuardrailIntegration {
  id: string;
  name: string;
  provider: Provider;
  default_action: Action;
  is_enabled: boolean;
  webhook_inbound_url: string;
  agent_ids: string[] | null;
  created_at: string;
}

interface GuardrailEvent {
  id: string;
  integration_id: string | null;
  agent_id: string | null;
  rule_name: string;
  severity: string;
  action_taken: Action;
  created_at: string;
}

interface GuardrailRule {
  id: string;
  name: string;
  description: string | null;
  integration_id: string | null;
  event_count_threshold: number;
  time_window_seconds: number;
  filter_agent_ids: string[] | null;
  filter_severities: string[] | null;
  filter_rule_names: string[] | null;
  action: Action;
  is_enabled: boolean;
  created_at: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────────
const PROVIDER_LABELS: Record<Provider, string> = {
  arize: "Arize AI", langfuse: "Langfuse", whylabs: "WhyLabs",
  fiddler: "Fiddler AI", custom: "Custom",
};

const ACTION_LABELS: Record<Action, string> = {
  alert_only: "Alert only",
  suspend_agent: "Suspend agent",
  revoke_jit_grants: "Revoke JIT grants",
  deny_all_policy: "Deny all (policy)",
  reduce_to_readonly: "Reduce to read-only",
};

const ACTION_SEVERITY: Record<Action, "info" | "warn" | "critical"> = {
  alert_only: "info",
  revoke_jit_grants: "warn",
  reduce_to_readonly: "warn",
  deny_all_policy: "critical",
  suspend_agent: "critical",
};

const SEV_COLORS = {
  info:     { bg: "rgba(99,102,241,0.12)",  text: "#818CF8", border: "rgba(99,102,241,0.25)" },
  warn:     { bg: "rgba(245,158,11,0.12)",  text: "#FCD34D", border: "rgba(245,158,11,0.25)" },
  critical: { bg: "rgba(239,68,68,0.12)",   text: "#F87171", border: "rgba(239,68,68,0.25)" },
};

function formatWindow(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function ActionBadge({ action }: { action: Action }) {
  const c = SEV_COLORS[ACTION_SEVERITY[action]];
  return (
    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}>
      {ACTION_LABELS[action]}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      title="Copy" className="shrink-0 p-1 rounded hover:bg-white/10 transition-colors"
      style={{ color: copied ? "#10B981" : "#94A3B8" }}>
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  );
}

// ── Create Integration Modal ─────────────────────────────────────────────────────
function CreateModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", provider: "arize", default_action: "alert_only", is_enabled: true,
    webhook_secret: "", api_endpoint: "",
  });
  const mut = useMutation({
    mutationFn: (data: typeof form) => api.post("/api/v1/guardrails", data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["guardrails"] }); onClose(); },
  });
  const inp = "w-full rounded-lg px-3 py-2 text-sm text-white bg-transparent border outline-none focus:border-indigo-500 transition-colors";
  const bdr = { border: "1px solid rgba(148,163,184,0.15)" };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
      <div className="w-full max-w-md rounded-2xl p-6 space-y-4"
        style={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)" }}>
        <h2 className="text-base font-bold text-white">Add Integration</h2>
        <div className="space-y-3">
          <input className={inp} style={bdr} placeholder="Name" value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          <select className={inp} style={bdr} value={form.provider}
            onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}>
            {Object.entries(PROVIDER_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select className={inp} style={bdr} value={form.default_action}
            onChange={e => setForm(f => ({ ...f, default_action: e.target.value }))}>
            {Object.entries(ACTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input className={inp} style={bdr} placeholder="Webhook secret (optional)"
            value={form.webhook_secret}
            onChange={e => setForm(f => ({ ...f, webhook_secret: e.target.value }))} />
          <input className={inp} style={bdr} placeholder="API endpoint (optional)"
            value={form.api_endpoint}
            onChange={e => setForm(f => ({ ...f, api_endpoint: e.target.value }))} />
        </div>
        {mut.isError && (
          <p className="text-xs text-red-400">Failed to create integration.</p>
        )}
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 btn-secondary text-sm">Cancel</button>
          <button onClick={() => mut.mutate(form)} disabled={!form.name || mut.isPending}
            className="flex-1 btn-primary text-sm disabled:opacity-50">
            {mut.isPending ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Integration Card ─────────────────────────────────────────────────────────────
function IntegrationCard({ item }: { item: GuardrailIntegration }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const toggle = useMutation({
    mutationFn: () => api.patch(`/api/v1/guardrails/${item.id}`, { is_enabled: !item.is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["guardrails"] }),
  });
  const del = useMutation({
    mutationFn: () => api.del(`/api/v1/guardrails/${item.id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["guardrails"] }),
  });
  return (
    <div className="rounded-xl overflow-hidden"
      style={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.10)" }}>
      <div className="px-4 py-3 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-white">{item.name}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded font-medium text-slate-400"
              style={{ background: "rgba(148,163,184,0.08)" }}>
              {PROVIDER_LABELS[item.provider]}
            </span>
            <ActionBadge action={item.default_action} />
            {!item.is_enabled && (
              <span className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                style={{ background: "rgba(100,116,139,0.15)", color: "#64748B" }}>disabled</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => toggle.mutate()}
            className="p-1 rounded hover:bg-white/8 transition-colors"
            style={{ color: item.is_enabled ? "#818CF8" : "#475569" }}
            title={item.is_enabled ? "Disable" : "Enable"}>
            {item.is_enabled ? <ToggleRight className="size-4" /> : <ToggleLeft className="size-4" />}
          </button>
          <button onClick={() => del.mutate()}
            className="p-1 rounded hover:bg-red-500/10 transition-colors text-slate-500 hover:text-red-400">
            <Trash2 className="size-3.5" />
          </button>
          <button onClick={() => setOpen(o => !o)}
            className="p-1 rounded hover:bg-white/8 transition-colors text-slate-500">
            {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
          </button>
        </div>
      </div>
      {open && (
        <div className="px-4 pb-4 pt-1 space-y-2"
          style={{ borderTop: "1px solid rgba(148,163,184,0.07)" }}>
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Inbound URL</p>
          <div className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}>
            <code className="text-[11px] text-indigo-300 flex-1 truncate">{item.webhook_inbound_url}</code>
            <CopyButton text={item.webhook_inbound_url} />
          </div>
          <p className="text-xs text-slate-500 pt-1">
            Paste this URL into your guardrail platform as the webhook destination.
            Kynara will receive events and enforce actions automatically.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Create Rule Modal ────────────────────────────────────────────────────────────
const SEVERITIES = ["critical", "warning", "info"];

function RuleModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    description: "",
    event_count_threshold: 5,
    time_window_seconds: 300,
    action: "revoke_jit_grants" as Action,
    filter_severities: [] as string[],
    filter_rule_names_raw: "",   // comma-separated input
    is_enabled: true,
  });

  const mut = useMutation({
    mutationFn: () => api.post("/api/v1/guardrails/rules", {
      name: form.name,
      description: form.description || null,
      event_count_threshold: form.event_count_threshold,
      time_window_seconds: form.time_window_seconds,
      action: form.action,
      filter_severities: form.filter_severities.length ? form.filter_severities : null,
      filter_rule_names: form.filter_rule_names_raw
        ? form.filter_rule_names_raw.split(",").map(s => s.trim()).filter(Boolean)
        : null,
      is_enabled: form.is_enabled,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["guardrail-rules"] }); onClose(); },
  });

  const inp = "w-full rounded-lg px-3 py-2 text-sm text-white bg-transparent border outline-none focus:border-indigo-500 transition-colors";
  const bdr = { border: "1px solid rgba(148,163,184,0.15)" };

  function toggleSev(s: string) {
    setForm(f => ({
      ...f,
      filter_severities: f.filter_severities.includes(s)
        ? f.filter_severities.filter(x => x !== s)
        : [...f.filter_severities, s],
    }));
  }

  const WINDOW_PRESETS = [
    { label: "1 min",  value: 60 },
    { label: "5 min",  value: 300 },
    { label: "15 min", value: 900 },
    { label: "1 hour", value: 3600 },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
      <div className="w-full max-w-lg rounded-2xl p-6 space-y-5"
        style={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)" }}>
        <div>
          <h2 className="text-base font-bold text-white">New Threshold Rule</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Define when Kynara should act — only after enough events accumulate in a time window.
          </p>
        </div>

        <div className="space-y-3">
          {/* Name */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Rule name</label>
            <input className={inp} style={bdr} placeholder="e.g. High-frequency toxicity block"
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Description (optional)</label>
            <input className={inp} style={bdr} placeholder="What does this rule protect against?"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          </div>

          {/* Threshold condition */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Trigger condition</label>
            <div className="rounded-xl p-4 space-y-3"
              style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.18)" }}>
              <p className="text-xs text-indigo-300 font-medium">
                Fire when{" "}
                <strong className="text-white">{form.event_count_threshold}</strong>{" "}
                or more matching events arrive within{" "}
                <strong className="text-white">{formatWindow(form.time_window_seconds)}</strong>
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-slate-500 mb-1">Event count</label>
                  <input type="number" min={1} max={1000}
                    className={inp} style={bdr}
                    value={form.event_count_threshold}
                    onChange={e => setForm(f => ({ ...f, event_count_threshold: parseInt(e.target.value) || 1 }))} />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-500 mb-1">Time window (seconds)</label>
                  <input type="number" min={10} max={86400}
                    className={inp} style={bdr}
                    value={form.time_window_seconds}
                    onChange={e => setForm(f => ({ ...f, time_window_seconds: parseInt(e.target.value) || 300 }))} />
                </div>
              </div>
              {/* Window presets */}
              <div className="flex gap-2">
                {WINDOW_PRESETS.map(p => (
                  <button key={p.value}
                    onClick={() => setForm(f => ({ ...f, time_window_seconds: p.value }))}
                    className="text-[10px] px-2 py-1 rounded-md transition-colors"
                    style={{
                      background: form.time_window_seconds === p.value
                        ? "rgba(99,102,241,0.25)" : "rgba(148,163,184,0.06)",
                      color: form.time_window_seconds === p.value ? "#818CF8" : "#64748B",
                      border: `1px solid ${form.time_window_seconds === p.value ? "rgba(99,102,241,0.4)" : "rgba(148,163,184,0.1)"}`,
                    }}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Action */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Action to take</label>
            <select className={inp} style={bdr} value={form.action}
              onChange={e => setForm(f => ({ ...f, action: e.target.value as Action }))}>
              {Object.entries(ACTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>

          {/* Severity filter */}
          <div>
            <label className="block text-xs text-slate-400 mb-1 flex items-center gap-1">
              <Filter className="size-3" /> Filter by severity (optional — leave blank for any)
            </label>
            <div className="flex gap-2">
              {SEVERITIES.map(s => {
                const active = form.filter_severities.includes(s);
                const c = s === "critical" ? SEV_COLORS.critical : s === "warning" ? SEV_COLORS.warn : SEV_COLORS.info;
                return (
                  <button key={s} onClick={() => toggleSev(s)}
                    className="text-[11px] px-3 py-1 rounded-full transition-all capitalize"
                    style={{
                      background: active ? c.bg : "rgba(148,163,184,0.06)",
                      color: active ? c.text : "#64748B",
                      border: `1px solid ${active ? c.border : "rgba(148,163,184,0.1)"}`,
                    }}>
                    {s}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Rule name filter */}
          <div>
            <label className="block text-xs text-slate-400 mb-1 flex items-center gap-1">
              <Filter className="size-3" /> Filter by rule names (optional — comma-separated)
            </label>
            <input className={inp} style={bdr}
              placeholder="toxicity_check, pii_leak, hallucination"
              value={form.filter_rule_names_raw}
              onChange={e => setForm(f => ({ ...f, filter_rule_names_raw: e.target.value }))} />
          </div>
        </div>

        {mut.isError && <p className="text-xs text-red-400">Failed to create rule.</p>}

        <div className="flex gap-3 pt-1">
          <button onClick={onClose} className="flex-1 btn-secondary text-sm">Cancel</button>
          <button onClick={() => mut.mutate()} disabled={!form.name || mut.isPending}
            className="flex-1 btn-primary text-sm disabled:opacity-50">
            {mut.isPending ? "Creating…" : "Create Rule"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Rules Section ────────────────────────────────────────────────────────────────
function RulesSection() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: rules = [], isLoading } = useQuery<GuardrailRule[]>({
    queryKey: ["guardrail-rules"],
    queryFn: () => api.get("/api/v1/guardrails/rules"),
  });

  const toggle = useMutation({
    mutationFn: (r: GuardrailRule) =>
      api.patch(`/api/v1/guardrails/rules/${r.id}`, { is_enabled: !r.is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["guardrail-rules"] }),
  });

  const del = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/guardrails/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["guardrail-rules"] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Zap className="size-4 text-yellow-400" />
            Threshold Rules
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Rules only fire when enough events accumulate — preventing false positives from single-event noise.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors"
          style={{ background: "rgba(99,102,241,0.12)", color: "#818CF8", border: "1px solid rgba(99,102,241,0.25)" }}>
          <Plus className="size-3.5" /> Add Rule
        </button>
      </div>

      {isLoading && <p className="text-xs text-slate-500">Loading…</p>}

      {!isLoading && rules.length === 0 && (
        <div className="rounded-xl p-6 text-center"
          style={{ background: "#0D1421", border: "1px dashed rgba(148,163,184,0.12)" }}>
          <Zap className="size-6 mx-auto mb-2 text-slate-600" />
          <p className="text-sm text-slate-400">No threshold rules yet</p>
          <p className="text-xs text-slate-600 mt-1">
            Add a rule to auto-revoke access only when a pattern repeats — e.g. 5 critical events in 5 minutes.
          </p>
        </div>
      )}

      <div className="space-y-2">
        {rules.map(rule => (
          <div key={rule.id} className="rounded-xl px-4 py-3 flex items-start gap-3"
            style={{ background: "#0D1421", border: `1px solid ${rule.is_enabled ? "rgba(148,163,184,0.10)" : "rgba(148,163,184,0.05)"}`, opacity: rule.is_enabled ? 1 : 0.55 }}>
            <div className="flex-1 min-w-0 space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-white">{rule.name}</span>
                <ActionBadge action={rule.action} />
              </div>
              {rule.description && (
                <p className="text-xs text-slate-500">{rule.description}</p>
              )}
              {/* Threshold pill */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(99,102,241,0.10)", color: "#818CF8", border: "1px solid rgba(99,102,241,0.2)" }}>
                  <Clock className="size-3" />
                  {rule.event_count_threshold} events in {formatWindow(rule.time_window_seconds)}
                </span>
                {rule.filter_severities && rule.filter_severities.length > 0 && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(148,163,184,0.06)", color: "#94A3B8", border: "1px solid rgba(148,163,184,0.1)" }}>
                    severity: {rule.filter_severities.join(", ")}
                  </span>
                )}
                {rule.filter_rule_names && rule.filter_rule_names.length > 0 && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(148,163,184,0.06)", color: "#94A3B8", border: "1px solid rgba(148,163,184,0.1)" }}>
                    rules: {rule.filter_rule_names.join(", ")}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button onClick={() => toggle.mutate(rule)}
                className="p-1 rounded hover:bg-white/8 transition-colors"
                style={{ color: rule.is_enabled ? "#818CF8" : "#475569" }}
                title={rule.is_enabled ? "Disable" : "Enable"}>
                {rule.is_enabled ? <ToggleRight className="size-4" /> : <ToggleLeft className="size-4" />}
              </button>
              <button onClick={() => del.mutate(rule.id)}
                className="p-1 rounded hover:bg-red-500/10 transition-colors text-slate-500 hover:text-red-400">
                <Trash2 className="size-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {showCreate && <RuleModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

// ── Events Table ─────────────────────────────────────────────────────────────────
function EventsTable() {
  const { data: events = [] } = useQuery<GuardrailEvent[]>({
    queryKey: ["guardrail-events"],
    queryFn: () => api.get("/api/v1/guardrails/events?limit=50"),
    refetchInterval: 15_000,
  });

  const SEV_ICON: Record<string, JSX.Element> = {
    critical: <XCircle className="size-3.5 text-red-400" />,
    warning:  <AlertTriangle className="size-3.5 text-yellow-400" />,
    info:     <CheckCircle2 className="size-3.5 text-indigo-400" />,
  };

  if (!events.length) return (
    <div className="px-4 py-8 text-center">
      <CheckCircle2 className="size-6 mx-auto mb-2 text-slate-700" />
      <p className="text-xs text-slate-500">No guardrail events yet</p>
    </div>
  );

  return (
    <table className="w-full text-xs">
      <thead>
        <tr style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
          {["Time", "Rule", "Severity", "Agent", "Action taken"].map(h => (
            <th key={h} className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {events.map((e, i) => (
          <tr key={e.id} style={{ borderBottom: i < events.length - 1 ? "1px solid rgba(148,163,184,0.05)" : "none" }}>
            <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">
              {new Date(e.created_at).toLocaleTimeString()}
            </td>
            <td className="px-4 py-2.5 text-slate-300 max-w-[180px] truncate">{e.rule_name}</td>
            <td className="px-4 py-2.5">
              <span className="flex items-center gap-1.5">
                {SEV_ICON[e.severity] ?? <Clock className="size-3.5 text-slate-500" />}
                <span className="capitalize text-slate-400">{e.severity}</span>
              </span>
            </td>
            <td className="px-4 py-2.5 font-mono text-slate-500 max-w-[120px] truncate">
              {e.agent_id ? e.agent_id.slice(0, 8) + "…" : "—"}
            </td>
            <td className="px-4 py-2.5">
              <ActionBadge action={e.action_taken} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────────
export default function GuardrailsPage() {
  const [showCreate, setShowCreate] = useState(false);

  const { data: integrations = [], isLoading } = useQuery<GuardrailIntegration[]>({
    queryKey: ["guardrails"],
    queryFn: () => api.get("/api/v1/guardrails"),
  });

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="size-5 text-indigo-400" />
            Guardrail Integrations
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Connect Arize AI, Langfuse, WhyLabs, Fiddler, or custom platforms.
            Define threshold rules to automatically revoke agent access when violations accumulate.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2 text-sm shrink-0">
          <Plus className="size-4" /> Add Integration
        </button>
      </div>

      {/* How it works callout */}
      <div className="rounded-xl p-4 flex gap-3"
        style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.18)" }}>
        <Zap className="size-4 text-yellow-400 mt-0.5 shrink-0" />
        <div className="space-y-1">
          <p className="text-xs font-semibold text-indigo-300">Threshold-based enforcement</p>
          <p className="text-xs text-slate-400">
            Events flow in from your guardrail platform via webhook. Kynara evaluates your{" "}
            <strong className="text-slate-200">threshold rules</strong> — acting only when the event count
            within a time window reaches your configured limit.
            This prevents false positives from single-event noise while still catching real patterns.
            Every enforcement is recorded in the tamper-evident audit log.
          </p>
        </div>
      </div>

      {/* Threshold Rules */}
      <RulesSection />

      {/* Integrations */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-200">Active Integrations</h2>
        {isLoading && <p className="text-xs text-slate-500">Loading…</p>}
        {!isLoading && integrations.length === 0 && (
          <div className="rounded-xl p-8 text-center"
            style={{ background: "#0D1421", border: "1px dashed rgba(148,163,184,0.15)" }}>
            <ShieldAlert className="size-8 mx-auto mb-2 text-slate-600" />
            <p className="text-sm text-slate-400">No integrations yet</p>
            <p className="text-xs text-slate-600 mt-1">Add your first guardrail integration above.</p>
          </div>
        )}
        {integrations.map(item => <IntegrationCard key={item.id} item={item} />)}
      </div>

      {/* Recent Events */}
      <div>
        <h2 className="text-sm font-semibold text-slate-200 mb-3">Recent Guardrail Events</h2>
        <div className="rounded-xl overflow-hidden"
          style={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.10)" }}>
          <EventsTable />
        </div>
      </div>

      {showCreate && <CreateModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
