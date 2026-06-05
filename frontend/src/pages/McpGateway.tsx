import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plug, Plus, Trash2, ShieldCheck, RefreshCw, AlertTriangle, X, Server, Eye,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

type McpServer = {
  id: string; name: string; slug: string; description: string | null;
  transport: string; url: string | null; stdio_cmd: string | null;
  scope_prefix: string; fail_mode: string; require_approval_default: boolean;
  is_enabled: boolean; last_synced_at: string | null; tool_count: number;
};
type McpTool = {
  id: string; name: string; description: string | null; scope: string;
  risk_class: string; effect_override: string | null; is_enabled: boolean;
};

const RISK = ["low", "medium", "high", "critical"];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="label">{label}</label>{children}</div>;
}

export default function McpGatewayPage() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [form, setForm] = useState<any>({
    name: "", transport: "sse", url: "", stdio_cmd: "",
    scope_prefix: "mcp", fail_mode: "closed", require_approval_default: false,
  });

  const { data: servers = [] } = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => api.get<McpServer[]>("/api/v1/mcp/servers"),
  });

  const create = useMutation({
    mutationFn: () => api.post("/api/v1/mcp/servers", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mcp-servers"] });
      setShowNew(false);
      setForm({ name: "", transport: "sse", url: "", stdio_cmd: "", scope_prefix: "mcp", fail_mode: "closed", require_approval_default: false });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/mcp/servers/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mcp-servers"] }); setSelected(null); },
  });

  return (
    <div>
      <PageHeader
        title="MCP Gateway"
        subtitle="Front your MCP servers with Kynara. Every tool call is authorized per-agent against your policies, and agents only see tools they're allowed to use."
        actions={
          <button className="btn-primary" onClick={() => setShowNew(true)}>
            <Plus className="size-4" /> Register server
          </button>
        }
      />

      <div className="px-8 py-6 space-y-4">
        {servers.length === 0 && (
          <div className="card p-10 text-center">
            <Plug className="size-8 mx-auto mb-3 text-ink-400" />
            <div className="text-sm font-medium text-ink-100">No MCP servers registered</div>
            <p className="text-xs text-ink-400 mt-1 max-w-md mx-auto">
              Register an upstream MCP server, point the Kynara wrapper at it, and every tool call
              will be governed by your policy engine.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {servers.map((s) => (
            <div key={s.id} className="card-hover p-5 cursor-pointer" onClick={() => setSelected(s.id)}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="size-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--s0-accent-subtle)" }}>
                    <Server className="size-4" style={{ color: "var(--s0-accent-text)" }} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-ink-50 truncate">{s.name}</div>
                    <div className="text-[11px] text-ink-400 font-mono truncate">{s.url || s.stdio_cmd || s.slug}</div>
                  </div>
                </div>
                <span className={s.is_enabled ? "pill-ok" : "pill-neutral"}>{s.is_enabled ? "enabled" : "disabled"}</span>
              </div>
              <div className="flex items-center gap-2 mt-3 text-[11px] text-ink-400">
                <span className="pill-info">{s.transport}</span>
                <span className="pill-neutral">{s.tool_count} tools</span>
                <span className={s.fail_mode === "closed" ? "pill-ok" : "pill-warn"}>fail-{s.fail_mode}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showNew && (
        <Modal title="Register MCP server" onClose={() => setShowNew(false)}>
          <div className="space-y-3">
            <Field label="Name">
              <input className="input" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Production CRM MCP" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Transport">
                <select className="input" value={form.transport}
                  onChange={(e) => setForm({ ...form, transport: e.target.value })}>
                  <option value="sse">sse</option>
                  <option value="http">http</option>
                  <option value="stdio">stdio</option>
                </select>
              </Field>
              <Field label="Scope prefix">
                <input className="input font-mono" value={form.scope_prefix}
                  onChange={(e) => setForm({ ...form, scope_prefix: e.target.value })} placeholder="mcp.crm" />
              </Field>
            </div>
            {form.transport === "stdio" ? (
              <Field label="Stdio command">
                <input className="input font-mono" value={form.stdio_cmd}
                  onChange={(e) => setForm({ ...form, stdio_cmd: e.target.value })}
                  placeholder="npx -y @modelcontextprotocol/server-foo" />
              </Field>
            ) : (
              <Field label="Upstream URL">
                <input className="input font-mono" value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  placeholder="https://your-mcp-server.example.com/sse" />
              </Field>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Fail mode">
                <select className="input" value={form.fail_mode}
                  onChange={(e) => setForm({ ...form, fail_mode: e.target.value })}>
                  <option value="closed">closed (deny on error)</option>
                  <option value="open">open (allow on error)</option>
                </select>
              </Field>
              <label className="flex items-center gap-2 text-sm text-ink-200 mt-6">
                <input type="checkbox" checked={form.require_approval_default}
                  onChange={(e) => setForm({ ...form, require_approval_default: e.target.checked })} />
                New tools require approval
              </label>
            </div>
            {create.isError && (
              <p className="text-[11px] text-danger-400 flex items-center gap-1">
                <AlertTriangle className="size-3" /> Could not create server. Check the URL/command and try again.
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setShowNew(false)}>Cancel</button>
              <button className="btn-primary" disabled={create.isPending || !form.name.trim()}
                onClick={() => create.mutate()}>
                {create.isPending ? "Creating…" : "Register"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {selected && (
        <ServerDetail
          serverId={selected}
          onClose={() => setSelected(null)}
          onDelete={() => remove.mutate(selected)}
        />
      )}
    </div>
  );
}

function ServerDetail({ serverId, onClose, onDelete }:
  { serverId: string; onClose: () => void; onDelete: () => void }) {
  const qc = useQueryClient();
  const [agentId, setAgentId] = useState("");
  const [preview, setPreview] = useState<any[] | null>(null);

  const { data } = useQuery({
    queryKey: ["mcp-server", serverId],
    queryFn: () => api.get<{ server: McpServer; tools: McpTool[] }>(`/api/v1/mcp/servers/${serverId}`),
  });

  const patchTool = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<McpTool> }) =>
      api.patch(`/api/v1/mcp/tools/${id}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mcp-server", serverId] }),
  });

  const runPreview = useMutation({
    mutationFn: () => api.get<{ tools: any[] }>(
      `/api/v1/mcp/servers/${serverId}/allowed-tools?subject_type=agent&subject_id=${encodeURIComponent(agentId)}`),
    onSuccess: (d) => setPreview(d.tools),
  });

  const server = data?.server;
  const tools = data?.tools || [];

  return (
    <Modal title={server?.name || "Server"} onClose={onClose} wide>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-xs text-ink-400">
            {server?.last_synced_at
              ? <>Last tool sync: {new Date(server.last_synced_at).toLocaleString()}</>
              : "No tools synced yet — start the Kynara wrapper pointed at this server."}
          </div>
          <button className="btn-danger text-xs" onClick={onDelete}>
            <Trash2 className="size-3.5" /> Delete
          </button>
        </div>

        {/* Tools + scope mapping */}
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b text-sm font-medium text-ink-100 flex items-center gap-2"
            style={{ borderColor: "var(--s0-border)" }}>
            <ShieldCheck className="size-4" style={{ color: "var(--s0-accent-text)" }} /> Tools &amp; scope mapping
          </div>
          {tools.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-ink-400 flex items-center justify-center gap-2">
              <RefreshCw className="size-3.5" /> Waiting for the wrapper to discover tools…
            </div>
          ) : (
            <table className="table">
              <thead><tr><th>Tool</th><th>Scope</th><th>Risk</th><th>Effect override</th><th>On</th></tr></thead>
              <tbody>
                {tools.map((t) => (
                  <tr key={t.id}>
                    <td className="font-mono text-xs text-ink-100">{t.name}</td>
                    <td>
                      <input className="input font-mono text-xs py-1" defaultValue={t.scope}
                        onBlur={(e) => e.target.value !== t.scope && patchTool.mutate({ id: t.id, patch: { scope: e.target.value } })} />
                    </td>
                    <td>
                      <select className="input text-xs py-1 w-24" defaultValue={t.risk_class}
                        onChange={(e) => patchTool.mutate({ id: t.id, patch: { risk_class: e.target.value } })}>
                        {RISK.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                    <td>
                      <select className="input text-xs py-1 w-36" defaultValue={t.effect_override || ""}
                        onChange={(e) => patchTool.mutate({ id: t.id, patch: { effect_override: e.target.value } })}>
                        <option value="">policy decides</option>
                        <option value="require_approval">require approval</option>
                        <option value="deny">always deny</option>
                      </select>
                    </td>
                    <td>
                      <input type="checkbox" checked={t.is_enabled}
                        onChange={(e) => patchTool.mutate({ id: t.id, patch: { is_enabled: e.target.checked } })} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Least-privilege preview */}
        <div className="card p-4">
          <div className="text-sm font-medium text-ink-100 flex items-center gap-2 mb-2">
            <Eye className="size-4" style={{ color: "var(--s0-accent-text)" }} /> Least-privilege preview
          </div>
          <p className="text-xs text-ink-400 mb-3">Enter an agent ID to see exactly which tools it would be allowed to call.</p>
          <div className="flex gap-2">
            <input className="input font-mono text-xs flex-1" placeholder="agent UUID"
              value={agentId} onChange={(e) => setAgentId(e.target.value)} />
            <button className="btn-secondary text-xs" disabled={!agentId || runPreview.isPending}
              onClick={() => runPreview.mutate()}>
              {runPreview.isPending ? "Checking…" : "Preview access"}
            </button>
          </div>
          {preview && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {preview.length === 0
                ? <span className="text-xs text-danger-400">No tools allowed for this agent.</span>
                : preview.map((t) => (
                  <span key={t.name} className={t.effect === "allow" ? "pill-ok" : "pill-warn"}>
                    {t.name}{t.effect === "require_approval" ? " (approval)" : ""}
                  </span>
                ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

function Modal({ title, children, onClose, wide }:
  { title: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(3px)" }} onClick={onClose}>
      <div className={`w-full ${wide ? "max-w-3xl" : "max-w-lg"} card p-6 max-h-[85vh] overflow-y-auto`}
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div className="text-base font-semibold text-ink-50">{title}</div>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-50"><X className="size-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
