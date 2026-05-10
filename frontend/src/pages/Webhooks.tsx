import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plug, Plus, Copy, Trash2, RotateCcw, CheckCircle2, AlertTriangle,
  Activity, Send,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

export default function WebhooksPage() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [freshSecret, setFreshSecret] = useState<{ url: string; secret: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const { data: endpoints = [] } = useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api.get<any[]>("/api/v1/webhooks"),
  });
  const { data: stats } = useQuery({
    queryKey: ["webhook-stats"],
    queryFn: () => api.get<any>("/api/v1/webhooks/stats"),
  });
  const { data: eventTypes } = useQuery({
    queryKey: ["webhook-event-types"],
    queryFn: () => api.get<any>("/api/v1/webhooks/event-types"),
  });

  const del = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/webhooks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }),
  });
  const rotate = useMutation({
    mutationFn: (id: string) => api.post<any>(`/api/v1/webhooks/${id}/rotate-secret`),
    onSuccess: (r) => setFreshSecret({ url: r.url, secret: r.secret }),
  });

  return (
    <div>
      <PageHeader
        title="Webhooks"
        subtitle="Subscribe an HTTPS endpoint to receive signed event deliveries."
        actions={
          <button className="btn-primary" onClick={() => setShowNew(true)}>
            <Plus className="size-4" /> Add endpoint
          </button>
        }
      />

      <div className="px-8 py-6 space-y-6">
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <Stat label="Delivered" value={stats.delivered} tone="ok" />
            <Stat label="Pending" value={stats.pending} tone="info" />
            <Stat label="Failed" value={stats.failed} tone="warn" />
            <Stat label="Dead-lettered" value={stats.dead} tone="danger" />
          </div>
        )}

        {freshSecret && (
          <div className="card p-4 border-warn-700 bg-warn-900/20">
            <div className="text-xs text-warn-300 mb-2">
              Copy this signing secret now — you won't see it again. Store in your
              endpoint's environment as <code className="font-mono">KYNARA_WEBHOOK_SECRET</code>.
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-ink-900 border border-ink-800 rounded p-2 text-xs font-mono break-all">
                {freshSecret.secret}
              </code>
              <button className="btn-ghost" onClick={() => navigator.clipboard.writeText(freshSecret.secret)}>
                <Copy className="size-4" />
              </button>
            </div>
            <button className="text-xs text-ink-400 mt-2" onClick={() => setFreshSecret(null)}>
              Dismiss
            </button>
          </div>
        )}

        {showNew && (
          <NewEndpointForm
            eventTypes={eventTypes?.event_types || []}
            onClose={() => setShowNew(false)}
            onCreated={(secret, url) => {
              setFreshSecret({ url, secret });
              setShowNew(false);
              qc.invalidateQueries({ queryKey: ["webhooks"] });
            }}
          />
        )}

        <div className="card overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th>Endpoint</th><th>Events</th><th>Last delivery</th><th>Health</th><th></th>
              </tr>
            </thead>
            <tbody>
              {endpoints.map((e) => (
                <tr key={e.id} className="cursor-pointer hover:bg-ink-900"
                    onClick={() => setSelected(selected === e.id ? null : e.id)}>
                  <td>
                    <div className="flex items-center gap-2">
                      <Plug className="size-4 text-accent-500" />
                      <div className="min-w-0">
                        <div className="text-sm font-mono truncate max-w-md">{e.url}</div>
                        <div className="text-[11px] text-ink-400">{e.description || "—"}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {(e.event_types || []).slice(0, 3).map((t: string) => (
                        <span key={t} className="pill pill-info font-mono text-[10px]">{t}</span>
                      ))}
                      {(e.event_types || []).length > 3 && (
                        <span className="pill text-[10px]">+{e.event_types.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="text-xs text-ink-400">
                    {e.last_success_at
                      ? <span className="pill-ok"><CheckCircle2 className="size-3" /> {new Date(e.last_success_at).toLocaleString()}</span>
                      : e.last_failure_at
                      ? <span className="pill-danger"><AlertTriangle className="size-3" /> failing</span>
                      : <span className="text-ink-500">never</span>}
                  </td>
                  <td>
                    {e.consecutive_failures > 0
                      ? <span className="pill-warn">{e.consecutive_failures} fails in a row</span>
                      : <span className="pill-ok">healthy</span>}
                  </td>
                  <td className="text-right">
                    <button className="btn-ghost text-xs" onClick={(ev) => { ev.stopPropagation(); rotate.mutate(e.id); }}>
                      <RotateCcw className="size-3.5" />
                    </button>
                    <button className="btn-ghost text-xs text-danger-400" onClick={(ev) => { ev.stopPropagation(); del.mutate(e.id); }}>
                      <Trash2 className="size-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {endpoints.length === 0 && (
                <tr><td colSpan={5} className="text-center text-ink-500 py-8 text-xs">
                  No webhooks configured.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        {selected && <DeliveriesPanel endpointId={selected} />}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  const cls = tone === "ok" ? "text-ok-500" : tone === "warn" ? "text-warn-500" : tone === "danger" ? "text-danger-500" : "text-accent-500";
  return (
    <div className="card p-4">
      <div className="text-[10px] uppercase tracking-wider text-ink-400">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${cls}`}>{value.toLocaleString()}</div>
    </div>
  );
}

function NewEndpointForm({ eventTypes, onClose, onCreated }:
  { eventTypes: string[]; onClose: () => void; onCreated: (secret: string, url: string) => void }) {
  const [url, setUrl] = useState("https://");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<string[]>(["decision.denied", "decision.approval_requested"]);

  const create = useMutation({
    mutationFn: () => api.post<any>("/api/v1/webhooks", {
      url, description, event_types: selected,
    }),
    onSuccess: (r) => onCreated(r.secret, r.url),
  });

  function toggle(t: string) {
    setSelected((s) => s.includes(t) ? s.filter((x) => x !== t) : [...s, t]);
  }

  return (
    <div className="card p-5">
      <div className="text-sm font-medium mb-4 flex items-center gap-2">
        <Send className="size-4 text-accent-500" /> New webhook endpoint
      </div>
      <div className="space-y-3">
        <div>
          <label className="label">Endpoint URL</label>
          <input className="input font-mono" value={url}
                 placeholder="https://your.app/webhooks/kynara"
                 onChange={(e) => setUrl(e.target.value)} />
        </div>
        <div>
          <label className="label">Description</label>
          <input className="input" value={description}
                 placeholder="prod alerting bridge"
                 onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div>
          <label className="label">Event types</label>
          <div className="flex flex-wrap gap-2">
            {eventTypes.map((t) => (
              <button key={t}
                      onClick={() => toggle(t)}
                      className={`pill font-mono text-[11px] ${selected.includes(t) ? "pill-info" : "pill-neutral"}`}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-3">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={!url.startsWith("https://") || selected.length === 0}
                  onClick={() => create.mutate()}>
            <Plus className="size-4" /> Create endpoint
          </button>
        </div>
      </div>
    </div>
  );
}

function DeliveriesPanel({ endpointId }: { endpointId: string }) {
  const qc = useQueryClient();
  const { data = [] } = useQuery({
    queryKey: ["webhook-deliveries", endpointId],
    queryFn: () => api.get<any[]>(`/api/v1/webhooks/${endpointId}/deliveries?limit=50`),
    refetchInterval: 5000,
  });
  const replay = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/webhooks/${endpointId}/deliveries/${id}/replay`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhook-deliveries", endpointId] }),
  });

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-ink-800">
        <div className="text-sm font-medium flex items-center gap-2">
          <Activity className="size-4 text-accent-500" /> Recent deliveries
        </div>
        <span className="text-[11px] text-ink-400">auto-refresh every 5s</span>
      </div>
      <table className="table">
        <thead><tr>
          <th>Event</th><th>Status</th><th>Attempts</th><th>HTTP</th><th>When</th><th>Error</th><th></th>
        </tr></thead>
        <tbody>
          {data.map((d: any) => (
            <tr key={d.id}>
              <td className="text-xs font-mono">{d.event_type}</td>
              <td>
                {d.status === "delivered" && <span className="pill-ok">delivered</span>}
                {d.status === "pending" && <span className="pill-info">pending</span>}
                {d.status === "failed" && <span className="pill-warn">failed</span>}
                {d.status === "dead" && <span className="pill-danger">dead</span>}
              </td>
              <td className="text-xs font-mono">{d.attempts}</td>
              <td className="text-xs font-mono">{d.last_response_status || "—"}</td>
              <td className="text-xs text-ink-400">
                {d.delivered_at ? new Date(d.delivered_at).toLocaleString() :
                 d.last_attempt_at ? new Date(d.last_attempt_at).toLocaleString() :
                 new Date(d.created_at).toLocaleString()}
              </td>
              <td className="text-xs text-ink-400 max-w-[280px] truncate" title={d.last_error || ""}>
                {d.last_error || "—"}
              </td>
              <td>
                {(d.status === "failed" || d.status === "dead") && (
                  <button className="btn-ghost text-xs" onClick={() => replay.mutate(d.id)}>
                    <RotateCcw className="size-3" /> Replay
                  </button>
                )}
              </td>
            </tr>
          ))}
          {data.length === 0 && (
            <tr><td colSpan={7} className="text-center text-ink-500 py-6 text-xs">No deliveries yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
