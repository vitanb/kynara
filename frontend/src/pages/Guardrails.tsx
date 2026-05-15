import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert, Plus, Trash2, ToggleLeft, ToggleRight,
  AlertTriangle, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp,
  ExternalLink, Copy, Check, Zap, Filter,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────────────────
type Provider = "arize" | "langfuse" | "whylabs" | "fiddler" | "custom"
  | "grafana" | "datadog" | "pagerduty" | "newrelic" | "prometheus";
type Action = "alert_only" | "disable_agent" | "suspend_agent" | "revoke_jit_grants" | "deny_all_policy" | "reduce_to_readonly";

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
  grafana: "Grafana", datadog: "Datadog", pagerduty: "PagerDuty",
  newrelic: "New Relic", prometheus: "Prometheus / Alertmanager",
  arize: "Arize AI", langfuse: "Langfuse", whylabs: "WhyLabs",
  fiddler: "Fiddler AI", custom: "Custom",
};

// Providers grouped for display
const PROVIDER_GROUPS = [
  { label: "Monitoring & Alerting", providers: ["grafana", "datadog", "pagerduty", "newrelic", "prometheus"] },
  { label: "AI / LLM Observability", providers: ["arize", "langfuse", "whylabs", "fiddler"] },
  { label: "Other", providers: ["custom"] },
] as const;

const ACTION_LABELS: Record<Action, string> = {
  alert_only: "Alert only",
  disable_agent: "Disable agent",
  suspend_agent: "Disable agent (legacy)",
  revoke_jit_grants: "Revoke JIT grants",
  deny_all_policy: "Deny all (policy)",
  reduce_to_readonly: "Reduce to read-only",
};

const ACTION_SEVERITY: Record<Action, "info" | "warn" | "critical"> = {
  alert_only: "info",
  revoke_jit_grants: "warn",
  reduce_to_readonly: "warn",
  deny_all_policy: "critical",
  disable_agent: "critical",
  suspend_agent: "critical",
};

// Kynara's stable inbound event format — every provider must send this shape
const KYNARA_PAYLOAD_SCHEMA = `{
  "agent_id":  "<agent UUID or slug>",  // required — which agent to act on
  "rule_name": "high_error_rate",       // required — the alert / check name
  "severity":  "critical",             // required — critical | warning | info
  "score":     0.95,                    // optional — numeric score 0–1
  "trace_id":  "trace-abc123",          // optional — for cross-referencing
  "message":   "Error rate exceeded…"  // optional — human-readable detail
}`;

// Per-provider webhook payload template — users paste this into their platform
const PROVIDER_TEMPLATES: Partial<Record<Provider, {
  label: string;
  where: string;
  template: string;
  templateLabel: string;
  note?: string;
}>> = {
  grafana: {
    label: "Grafana Alerting",
    where: "Alerting → Notification templates → New template, then set the Webhook contact point Message field to: {{ template \"kynara\" . }}",
    templateLabel: "Notification template (Go template syntax)",
    template: `{{ define "kynara" -}}
{
  "agent_id":  "{{ .CommonLabels.kynara_agent_id }}",
  "rule_name": "{{ .CommonLabels.alertname }}",
  "severity":  "{{ if .CommonLabels.severity }}{{ .CommonLabels.severity }}{{ else }}critical{{ end }}",
  "message":   "{{ .CommonAnnotations.summary }}"
}
{{- end }}`,
    note: "Add labels kynara_agent_id=<agent-uuid> and severity=critical|warning|info to each alert rule.",
  },
  datadog: {
    label: "Datadog Webhooks",
    where: "Integrations → Webhooks → New Webhook → Custom Payload",
    templateLabel: "Custom Payload JSON",
    template: `{
  "agent_id":  "$kynara_agent_id",
  "rule_name": "$alert_title",
  "severity":  "$alert_type",
  "score":     "$alert_metric",
  "trace_id":  "$id",
  "message":   "$text_only_msg"
}`,
    note: "Tag your monitor with kynara_agent_id:<agent-uuid>. Trigger with @webhook-<name> in the monitor message.",
  },
  newrelic: {
    label: "New Relic Alerts",
    where: "Alerts → Notification channels → Webhook → Custom Payload",
    templateLabel: "Custom Payload JSON",
    template: `{
  "agent_id":  "{{ $labels.kynara_agent_id }}",
  "rule_name": "{{ $labels.conditionName }}",
  "severity":  "{{ $labels.priority }}",
  "score":     {{ $value }},
  "trace_id":  "{{ $labels.incidentId }}",
  "message":   "{{ $labels.conditionDescription }}"
}`,
    note: "Add a tag kynara_agent_id=<agent-uuid> to the monitored entity or condition.",
  },
  prometheus: {
    label: "Prometheus / Alertmanager",
    where: "alertmanager.yml → receivers — add a webhook_configs entry pointing to the Inbound URL",
    templateLabel: "alertmanager.yml snippet",
    template: `receivers:
  - name: kynara
    webhook_configs:
      - url: '<paste Inbound URL here>'
        send_resolved: false

# In your Prometheus alert rule, add these labels:
# kynara_agent_id: "<agent-uuid>"
# severity: "critical"   # or warning | info
#
# Then run a small adapter sidecar that maps:
#   labels.kynara_agent_id → agent_id
#   labels.alertname       → rule_name
#   labels.severity        → severity`,
    note: "Alertmanager doesn't support custom webhook bodies natively. A minimal adapter (e.g. a 10-line AWS Lambda or Cloud Function) reshapes the payload before forwarding to Kynara.",
  },
  pagerduty: {
    label: "PagerDuty",
    where: "Event Orchestration → Webhook endpoint, or use a small Lambda/Cloud Function as a bridge",
    templateLabel: "Bridge function (Python)",
    template: `import json, urllib.request

KYNARA_URL = "<paste Inbound URL here>"

def handler(event, context):
    pd = json.loads(event["body"])
    incident = pd["messages"][0]["incident"]
    payload = {
        "agent_id":  incident.get("custom_fields", {}).get("kynara_agent_id"),
        "rule_name": incident.get("title", "unknown"),
        "severity":  "critical" if incident.get("urgency") == "high" else "warning",
        "trace_id":  incident.get("id"),
        "message":   incident.get("summary"),
    }
    req = urllib.request.Request(
        KYNARA_URL, json.dumps(payload).encode(),
        {"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req)
    return {"statusCode": 200}`,
    note: "Add a custom field kynara_agent_id on PagerDuty incidents to route events to a specific agent.",
  },
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
    name: "", provider: "grafana", default_action: "alert_only", is_enabled: true,
    webhook_secret: "", api_endpoint: "",
  });
  const mut = useMutation({
    mutationFn: (data: typeof form) => api.post("/api/v1/guardrails", data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["guardrails"] }); onClose(); },
  });
  const inp = "w-full rounded-lg px-3 py-2 text-sm text-white border outline-none focus:border-indigo-500 transition-colors";
  const bdr = { border: "1px solid rgba(148,163,184,0.15)", background: "#0D1421", color: "#F1F5F9" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
      <div className="w-full max-w-lg rounded-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto"
        style={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)" }}>
        <h2 className="text-base font-bold text-white">Add Integration</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <input className={inp} style={bdr} placeholder="e.g. Grafana Production Alerts" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Platform</label>
            <select className={inp} style={bdr} value={form.provider}
              onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}>
              {PROVIDER_GROUPS.map(g => (
                <optgroup key={g.label} label={g.label} style={{ background: "#0D1421", color: "#94A3B8" }}>
                  {g.providers.map(p => (
                    <option key={p} value={p} style={{ background: "#0D1421", color: "#F1F5F9" }}>
                      {PROVIDER_LABELS[p as Provider]}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Default action (when no rule matches)</label>
            <select className={inp} style={bdr} value={form.default_action}
              onChange={e => setForm(f => ({ ...f, default_action: e.target.value }))}>
              {Object.entries(ACTION_LABELS)
                .filter(([v]) => v !== "suspend_agent")
                .map(([v, l]) => <option key={v} value={v} style={{ background: "#0D1421", color: "#F1F5F9" }}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Webhook secret <span className="text-slate-600">(optional — used to verify requests)</span></label>
            <input className={inp} style={bdr} placeholder="Shared secret for HMAC verification"
              value={form.webhook_secret}
              onChange={e => setForm(f => ({ ...f, webhook_secret: e.target.value }))} />
          </div>

          {/* Format reminder */}
          <div className="rounded-xl p-3 space-y-1"
            style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.18)" }}>
            <p className="text-xs font-semibold text-indigo-300">After creating, expand the integration card to get:</p>
            <ul className="text-xs text-slate-400 space-y-0.5 pl-3">
              <li>• The inbound URL to paste into {PROVIDER_TEMPLATES[form.provider as Provider]?.label ?? form.provider}</li>
              <li>• The Kynara JSON payload format your platform must send</li>
              <li>• A copy-paste webhook template for {PROVIDER_TEMPLATES[form.provider as Provider]?.label ?? form.provider}</li>
            </ul>
          </div>
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
        <div className="px-4 pb-4 pt-3 space-y-4"
          style={{ borderTop: "1px solid rgba(148,163,184,0.07)" }}>

          {/* Step 1 — Inbound URL */}
          <div>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Step 1 — Paste this URL into {PROVIDER_TEMPLATES[item.provider]?.label ?? PROVIDER_LABELS[item.provider]}
            </p>
            <div className="flex items-center gap-2 rounded-lg px-3 py-2"
              style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}>
              <code className="text-[11px] text-indigo-300 flex-1 truncate">{item.webhook_inbound_url}</code>
              <CopyButton text={item.webhook_inbound_url} />
            </div>
            {PROVIDER_TEMPLATES[item.provider] && (
              <p className="text-[10px] text-slate-500 mt-1.5">
                Where: <span className="text-slate-400">{PROVIDER_TEMPLATES[item.provider]!.where}</span>
              </p>
            )}
          </div>

          {/* Step 2 — Kynara payload format */}
          <div>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Step 2 — Kynara inbound format <span className="normal-case font-normal text-slate-600">(stable — never changes)</span>
            </p>
            <div className="rounded-lg overflow-hidden" style={{ border: "1px solid rgba(148,163,184,0.1)" }}>
              <div className="flex items-center justify-between px-3 py-1.5"
                style={{ background: "rgba(148,163,184,0.05)", borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
                <span className="text-[10px] font-mono text-slate-500">application/json</span>
                <CopyButton text={KYNARA_PAYLOAD_SCHEMA} />
              </div>
              <pre className="text-[10px] font-mono text-slate-300 px-3 py-2.5 overflow-x-auto leading-relaxed"
                style={{ background: "#080E1A" }}>
                {KYNARA_PAYLOAD_SCHEMA}
              </pre>
            </div>
          </div>

          {/* Step 3 — Provider-specific template */}
          {PROVIDER_TEMPLATES[item.provider] && (
            <div>
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Step 3 — Configure {PROVIDER_TEMPLATES[item.provider]!.label} to send in Kynara format
              </p>
              <div className="rounded-lg overflow-hidden" style={{ border: "1px solid rgba(99,102,241,0.2)" }}>
                <div className="flex items-center justify-between px-3 py-1.5"
                  style={{ background: "rgba(99,102,241,0.06)", borderBottom: "1px solid rgba(99,102,241,0.12)" }}>
                  <span className="text-[10px] font-medium text-indigo-300">
                    {PROVIDER_TEMPLATES[item.provider]!.templateLabel}
                  </span>
                  <CopyButton text={PROVIDER_TEMPLATES[item.provider]!.template} />
                </div>
                <pre className="text-[10px] font-mono text-indigo-200 px-3 py-2.5 overflow-x-auto leading-relaxed"
                  style={{ background: "#080E1A" }}>
                  {PROVIDER_TEMPLATES[item.provider]!.template}
                </pre>
              </div>
              {PROVIDER_TEMPLATES[item.provider]!.note && (
                <p className="text-[10px] text-slate-500 mt-1.5 flex items-start gap-1">
                  <span className="shrink-0 mt-px">💡</span>
                  {PROVIDER_TEMPLATES[item.provider]!.note}
                </p>
              )}
            </div>
          )}

          {/* Generic fallback for providers without a template */}
          {!PROVIDER_TEMPLATES[item.provider] && (
            <p className="text-[10px] text-slate-500">
              Configure your platform's webhook to POST the Kynara format above to the inbound URL.
              The format is stable — Kynara will never change it to match provider-specific schemas.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Create Rule Modal ────────────────────────────────────────────────────────────
const SEVERITIES = ["critical", "warning", "info"];

// Quick-setup presets
const RULE_PRESETS = [
  {
    label: "Disable agent immediately",
    description: "Disable the agent the moment a single critical event arrives.",
    icon: "🚫",
    patch: { action: "disable_agent" as Action, event_count_threshold: 1, time_window_seconds: 60, filter_severities: ["critical"] },
  },
  {
    label: "Disable after repeated violations",
    description: "Disable after 5 critical events in 5 minutes.",
    icon: "⚡",
    patch: { action: "disable_agent" as Action, event_count_threshold: 5, time_window_seconds: 300, filter_severities: ["critical"] },
  },
  {
    label: "Revoke JIT on warning",
    description: "Strip JIT grants when 3 warnings arrive in 10 minutes.",
    icon: "🔑",
    patch: { action: "revoke_jit_grants" as Action, event_count_threshold: 3, time_window_seconds: 600, filter_severities: ["critical", "warning"] },
  },
  {
    label: "Read-only on anomaly",
    description: "Reduce to read-only when any event fires.",
    icon: "👁",
    patch: { action: "reduce_to_readonly" as Action, event_count_threshold: 1, time_window_seconds: 300, filter_severities: [] },
  },
];

function RuleModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    description: "",
    event_count_threshold: 1,
    time_window_seconds: 60,
    action: "disable_agent" as Action,
    filter_severities: ["critical"] as string[],
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

  const inp = "w-full rounded-lg px-3 py-2 text-sm text-white border outline-none focus:border-indigo-500 transition-colors";
  const bdr = { border: "1px solid rgba(148,163,184,0.15)", background: "#0D1421", color: "#F1F5F9" };

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
          <h2 className="text-base font-bold text-white">New Rule</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Define when Kynara should act — only after enough events accumulate in a time window.
          </p>
        </div>

        {/* Quick presets */}
        <div>
          <p className="text-xs text-slate-500 mb-2">Quick setup</p>
          <div className="grid grid-cols-2 gap-2">
            {RULE_PRESETS.map(preset => (
              <button
                key={preset.label}
                type="button"
                onClick={() => setForm(f => ({ ...f, ...preset.patch, name: f.name || preset.label }))}
                className="text-left rounded-xl px-3 py-2.5 transition-colors hover:bg-white/5"
                style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}
              >
                <div className="text-sm mb-0.5">{preset.icon} <span className="text-xs font-semibold text-slate-200">{preset.label}</span></div>
                <p className="text-[10px] text-slate-500 leading-snug">{preset.description}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          {/* Name */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Rule name</label>
            <input className={inp} style={bdr} placeholder="e.g. Disable agent on critical alert"
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
            <label className="block text-xs text-slate-400 mb-1">Action to take when rule fires</label>
            <select className={inp} style={bdr} value={form.action}
              onChange={e => setForm(f => ({ ...f, action: e.target.value as Action }))}>
              {Object.entries(ACTION_LABELS)
                .filter(([v]) => v !== "suspend_agent")
                .map(([v, l]) => <option key={v} value={v} style={{ background: "#0D1421", color: "#F1F5F9" }}>{l}</option>)}
            </select>
            {form.action === "disable_agent" && (
              <p className="text-[10px] text-orange-400 mt-1 flex items-center gap-1">
                <AlertTriangle className="size-3 shrink-0" />
                Agent will be set to inactive — it won't be able to make policy decisions until re-enabled manually.
              </p>
            )}
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
            Connect Grafana, Datadog, PagerDuty, Prometheus, Arize AI, Langfuse, and more.
            Define threshold rules to automatically disable agents or revoke access when alerts fire.
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
            Events flow in from Grafana, Datadog, PagerDuty, or any monitoring platform via webhook.
            Kynara evaluates your <strong className="text-slate-200">threshold rules</strong> — acting only
            when the event count within a time window reaches your limit. You can{" "}
            <strong className="text-slate-200">disable an agent instantly</strong> on a single critical alert,
            or only after repeated violations. Every enforcement is recorded in the tamper-evident audit log.
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
