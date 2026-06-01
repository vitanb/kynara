import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  MessageSquare, CheckCircle2, AlertCircle, Loader2,
  Eye, EyeOff, Trash2, Send, ExternalLink,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface IntegrationConfig {
  slack_enabled: boolean;
  slack_channel_id: string | null;
  slack_bot_token_set: boolean;
  slack_signing_secret_set: boolean;
  slack_webhook_url_set: boolean;
  teams_enabled: boolean;
  teams_webhook_url_set: boolean;
  teams_callback_secret_set: boolean;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchConfig(): Promise<IntegrationConfig> {
  return api.get<IntegrationConfig>("/api/v1/integrations/config");
}

async function saveConfig(body: object): Promise<IntegrationConfig> {
  return api.put<IntegrationConfig>("/api/v1/integrations/config", body);
}

async function testConfig(): Promise<Record<string, string>> {
  return api.post<Record<string, string>>("/api/v1/integrations/config/test");
}

async function deleteSlack(): Promise<void> { await api.del<void>("/api/v1/integrations/config/slack"); }
async function deleteTeams(): Promise<void> { await api.del<void>("/api/v1/integrations/config/teams"); }

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={ok
        ? { background: "rgba(16,185,129,.12)", color: "#34D399", border: "1px solid rgba(16,185,129,.3)" }
        : { background: "rgba(148,163,184,.08)", color: "#64748B", border: "1px solid rgba(148,163,184,.12)" }
      }>
      {ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
      {label}
    </span>
  );
}

function SecretInput({ label, placeholder, value, onChange, helpText }: {
  label: string; placeholder: string; value: string;
  onChange: (v: string) => void; helpText?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wide">{label}</label>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg px-3 pr-10 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 outline-none font-mono"
          style={{ background: "rgba(148,163,184,.05)", border: "1px solid rgba(148,163,184,.12)" }}
        />
        <button type="button" onClick={() => setShow(s => !s)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
          {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
        </button>
      </div>
      {helpText && <p className="text-xs text-slate-600 mt-1">{helpText}</p>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const { data: cfg, isLoading } = useQuery({ queryKey: ["integration-config"], queryFn: fetchConfig });

  // Slack state
  const [slackToken, setSlackToken] = useState("");
  const [slackSecret, setSlackSecret] = useState("");
  const [slackChannel, setSlackChannel] = useState("");
  const [slackWebhook, setSlackWebhook] = useState("");
  const [slackEnabled, setSlackEnabled] = useState(true);

  // Teams state
  const [teamsWebhook, setTeamsWebhook] = useState("");
  const [teamsSecret, setTeamsSecret] = useState("");
  const [teamsEnabled, setTeamsEnabled] = useState(true);

  const [testResult, setTestResult] = useState<Record<string, string> | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const saveMutation = useMutation({
    mutationFn: saveConfig,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integration-config"] });
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2500);
    },
    onError: () => setSaveStatus("error"),
  });

  const testMutation = useMutation({
    mutationFn: testConfig,
    onSuccess: (data) => setTestResult(data),
  });

  const delSlackMutation = useMutation({ mutationFn: deleteSlack, onSuccess: () => qc.invalidateQueries({ queryKey: ["integration-config"] }) });
  const delTeamsMutation = useMutation({ mutationFn: deleteTeams, onSuccess: () => qc.invalidateQueries({ queryKey: ["integration-config"] }) });

  function handleSave() {
    setSaveStatus("saving");
    const body: Record<string, object> = {};
    const hasSlack = slackToken || slackWebhook || slackChannel;
    if (hasSlack) {
      body.slack = {
        ...(slackToken && { bot_token: slackToken }),
        ...(slackSecret && { signing_secret: slackSecret }),
        ...(slackChannel && { channel_id: slackChannel }),
        ...(slackWebhook && { webhook_url: slackWebhook }),
        enabled: slackEnabled,
      };
    }
    if (teamsWebhook) {
      body.teams = {
        webhook_url: teamsWebhook,
        ...(teamsSecret && { callback_secret: teamsSecret }),
        enabled: teamsEnabled,
      };
    }
    saveMutation.mutate(body);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
      </div>
    );
  }

  const card = "rounded-2xl p-7";
  const cardStyle = { background: "var(--s0-surface, #080C14)", border: "1px solid rgba(148,163,184,.1)" };
  const sectionTag = "text-xs font-bold uppercase tracking-widest text-indigo-400 mb-3";
  const inputLabel = "block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wide";
  const input = "w-full rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 outline-none";
  const inputStyle = { background: "rgba(148,163,184,.05)", border: "1px solid rgba(148,163,184,.12)" };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">

      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: "rgba(99,102,241,.15)", border: "1px solid rgba(99,102,241,.25)" }}>
            <MessageSquare className="w-4.5 h-4.5 text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Integrations</h1>
        </div>
        <p className="text-sm text-slate-400 ml-12">
          When an agent action requires human approval, Kynara posts a notification to your
          Slack channel or Teams workspace so reviewers can approve or reject directly from chat.
        </p>
      </div>

      {/* Current status */}
      {cfg && (
        <div className={card} style={cardStyle}>
          <div className={sectionTag}>Current status</div>
          <div className="flex flex-wrap gap-3">
            <StatusPill ok={cfg.slack_enabled && cfg.slack_bot_token_set} label={cfg.slack_enabled ? "Slack connected" : "Slack not configured"} />
            <StatusPill ok={cfg.teams_enabled && cfg.teams_webhook_url_set} label={cfg.teams_enabled ? "Teams connected" : "Teams not configured"} />
            {cfg.slack_channel_id && (
              <span className="text-xs text-slate-500 self-center">Channel: <code className="text-slate-400">{cfg.slack_channel_id}</code></span>
            )}
          </div>
        </div>
      )}

      {/* Slack */}
      <div className={card} style={cardStyle}>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#4A154B] flex items-center justify-center text-white font-bold text-sm">S</div>
            <div>
              <div className="font-semibold text-white">Slack</div>
              <div className="text-xs text-slate-500">Interactive approve/reject buttons in your channel</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {cfg?.slack_bot_token_set && (
              <button onClick={() => delSlackMutation.mutate()}
                className="text-xs text-slate-500 hover:text-red-400 flex items-center gap-1 transition-colors"
                disabled={delSlackMutation.isPending}>
                <Trash2 className="w-3 h-3" /> Remove
              </button>
            )}
            <label className="flex items-center gap-2 cursor-pointer">
              <div className={`w-9 h-5 rounded-full transition-colors relative ${slackEnabled ? "bg-indigo-500" : "bg-slate-700"}`}
                onClick={() => setSlackEnabled(e => !e)}>
                <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${slackEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
              </div>
              <span className="text-xs text-slate-400">Enabled</span>
            </label>
          </div>
        </div>

        <div className="space-y-4">
          <div className={`text-xs text-slate-500 p-3 rounded-lg mb-2`} style={{ background: "rgba(99,102,241,.06)", border: "1px solid rgba(99,102,241,.15)" }}>
            <strong className="text-slate-400">Setup:</strong> Create a Slack app at{" "}
            <a href="https://api.slack.com/apps" target="_blank" rel="noopener" className="text-indigo-400 hover:underline">
              api.slack.com/apps <ExternalLink className="inline w-2.5 h-2.5" />
            </a>
            {" "}with <code>chat:write</code> scope. Enable Interactivity → set Request URL to{" "}
            <code className="text-slate-300">https://kynaraai.com/api/v1/integrations/slack/callback</code>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SecretInput label="Bot Token" placeholder="xoxb-..." value={slackToken} onChange={setSlackToken}
              helpText={cfg?.slack_bot_token_set ? "✓ Token saved — enter new value to rotate" : "From OAuth & Permissions page"} />
            <SecretInput label="Signing Secret" placeholder="From Basic Information" value={slackSecret} onChange={setSlackSecret}
              helpText={cfg?.slack_signing_secret_set ? "✓ Secret saved — enter new value to rotate" : "Used to verify callback signatures"} />
          </div>
          <div>
            <label className={inputLabel}>Channel ID</label>
            <input className={input} style={inputStyle} placeholder="C08XXXXXXX"
              value={slackChannel} onChange={e => setSlackChannel(e.target.value)} />
            <p className="text-xs text-slate-600 mt-1">Right-click a channel in Slack → View channel details → copy the ID at the bottom</p>
          </div>
          <div className="relative">
            <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-slate-800" />
            <div className="relative text-center"><span className="text-xs text-slate-600 bg-[#080C14] px-3">or use an Incoming Webhook instead of a Bot Token</span></div>
          </div>
          <SecretInput label="Incoming Webhook URL (optional)" placeholder="https://hooks.slack.com/services/..." value={slackWebhook} onChange={setSlackWebhook}
            helpText={cfg?.slack_webhook_url_set ? "✓ Webhook saved — simpler but no interactive buttons" : "Simpler setup — no interactive buttons"} />
        </div>
      </div>

      {/* Teams */}
      <div className={card} style={cardStyle}>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#4B53BC] flex items-center justify-center text-white font-bold text-sm">T</div>
            <div>
              <div className="font-semibold text-white">Microsoft Teams</div>
              <div className="text-xs text-slate-500">Post approval cards to a Teams channel</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {cfg?.teams_webhook_url_set && (
              <button onClick={() => delTeamsMutation.mutate()}
                className="text-xs text-slate-500 hover:text-red-400 flex items-center gap-1 transition-colors"
                disabled={delTeamsMutation.isPending}>
                <Trash2 className="w-3 h-3" /> Remove
              </button>
            )}
            <label className="flex items-center gap-2 cursor-pointer">
              <div className={`w-9 h-5 rounded-full transition-colors relative ${teamsEnabled ? "bg-indigo-500" : "bg-slate-700"}`}
                onClick={() => setTeamsEnabled(e => !e)}>
                <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${teamsEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
              </div>
              <span className="text-xs text-slate-400">Enabled</span>
            </label>
          </div>
        </div>

        <div className="space-y-4">
          <div className="text-xs text-slate-500 p-3 rounded-lg" style={{ background: "rgba(75,83,188,.06)", border: "1px solid rgba(75,83,188,.2)" }}>
            <strong className="text-slate-400">Setup:</strong> In Teams, open the channel → ··· → Connectors → Incoming Webhook → Create → copy the URL below.
          </div>
          <SecretInput label="Incoming Webhook URL" placeholder="https://...webhook.office.com/webhookb2/..." value={teamsWebhook} onChange={setTeamsWebhook}
            helpText={cfg?.teams_webhook_url_set ? "✓ Webhook saved — enter new value to rotate" : "Required"} />
          <SecretInput label="Callback Secret (optional)" placeholder="Shared secret for Power Automate" value={teamsSecret} onChange={setTeamsSecret}
            helpText="Only needed if using Power Automate for interactive approve/reject buttons" />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => { setTestResult(null); testMutation.mutate(); }}
          disabled={testMutation.isPending || (!cfg?.slack_bot_token_set && !cfg?.slack_webhook_url_set && !cfg?.teams_webhook_url_set)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white transition-colors disabled:opacity-40"
          style={{ border: "1px solid rgba(148,163,184,.15)" }}>
          {testMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          Send test notification
        </button>

        <button onClick={handleSave} disabled={saveStatus === "saving"}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-60"
          style={{ background: "linear-gradient(135deg,#4F46E5,#6D28D9)", boxShadow: "0 4px 14px rgba(79,70,229,.3)" }}>
          {saveStatus === "saving" && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {saveStatus === "saved" ? "✓ Saved" : saveStatus === "error" ? "Error — retry" : "Save integration"}
        </button>
      </div>

      {/* Test result */}
      {testResult && (
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(99,102,241,.06)", border: "1px solid rgba(99,102,241,.2)" }}>
          <div className="font-semibold text-white mb-2">Test result</div>
          {Object.entries(testResult).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2">
              {v === "ok" ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <AlertCircle className="w-3.5 h-3.5 text-slate-500" />}
              <span className="text-slate-400 capitalize">{k}:</span>
              <span className={v === "ok" ? "text-emerald-400" : "text-slate-500"}>{v === "ok" ? "Message sent successfully" : v}</span>
            </div>
          ))}
        </div>
      )}

      {/* How it works */}
      <div className={card} style={{ ...cardStyle, padding: "20px 24px" }}>
        <div className={sectionTag}>How it works</div>
        <ol className="space-y-2 text-sm text-slate-400">
          <li className="flex gap-3"><span className="text-indigo-400 font-bold flex-shrink-0">1.</span>An AI agent calls an action that matches a <code className="text-slate-300">require_approval</code> policy.</li>
          <li className="flex gap-3"><span className="text-indigo-400 font-bold flex-shrink-0">2.</span>Kynara posts a notification to your Slack channel or Teams workspace with the agent, action, resource, and expiry time.</li>
          <li className="flex gap-3"><span className="text-indigo-400 font-bold flex-shrink-0">3.</span><span>In Slack, reviewers click <strong className="text-white">✓ Approve</strong> or <strong className="text-white">✗ Reject</strong> directly in the message — no need to open Kynara. In Teams, buttons open the Kynara approval page.</span></li>
          <li className="flex gap-3"><span className="text-indigo-400 font-bold flex-shrink-0">4.</span>The message updates to show who approved or rejected, and the agent either continues or is halted.</li>
        </ol>
      </div>

    </div>
  );
}
