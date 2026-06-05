import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Fingerprint, Plus, Trash2, RefreshCw, CheckCircle2, AlertTriangle, X, Plug, Users,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

type Provider = {
  id: string; name: string; provider: string; base_url: string; has_token: boolean;
  sync_mode: string; group_id: string | null; default_mode: string;
  role_mapping: Record<string, string>; default_on_behalf_user_id: string | null;
  deactivate_missing: boolean; is_enabled: boolean;
  last_synced_at: string | null; last_sync_status: string | null;
  last_sync_stats: Record<string, any>;
};

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-ink-500 mt-1">{hint}</p>}
    </div>
  );
}

export default function IdentityProvidersPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Provider | "new" | null>(null);

  const { data: providers = [] } = useQuery({
    queryKey: ["idp-providers"],
    queryFn: () => api.get<Provider[]>("/api/v1/idp/providers"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/idp/providers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["idp-providers"] }),
  });

  return (
    <div>
      <PageHeader
        title="Identity Providers"
        subtitle="Sync AI-agent identities from Okta into Kynara. Imported agents are governed by your policies; Okta groups can map to Kynara roles."
        actions={
          <button className="btn-primary" onClick={() => setEditing("new")}>
            <Plus className="size-4" /> Connect Okta
          </button>
        }
      />

      <div className="px-8 py-6 space-y-4">
        {providers.length === 0 && (
          <div className="card p-10 text-center">
            <Fingerprint className="size-8 mx-auto mb-3 text-ink-400" />
            <div className="text-sm font-medium text-ink-100">No identity providers connected</div>
            <p className="text-xs text-ink-400 mt-1 max-w-md mx-auto">
              Connect Okta to automatically import and keep your AI-agent identities in sync.
            </p>
          </div>
        )}

        {providers.map((p) => (
          <div key={p.id} className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="size-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: "var(--s0-accent-subtle)" }}>
                  <Plug className="size-4" style={{ color: "var(--s0-accent-text)" }} />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-ink-50 truncate">{p.name}</div>
                  <div className="text-[11px] text-ink-400 font-mono truncate">{p.base_url}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={p.is_enabled ? "pill-ok" : "pill-neutral"}>{p.is_enabled ? "enabled" : "disabled"}</span>
                <span className="pill-info">{p.sync_mode}</span>
              </div>
            </div>

            <div className="flex items-center gap-4 mt-4 text-[11px] text-ink-400">
              {p.last_synced_at ? (
                <>
                  <span className={p.last_sync_status === "ok" ? "pill-ok" : "pill-danger"}>
                    {p.last_sync_status === "ok" ? "last sync ok" : "last sync error"}
                  </span>
                  <span>created {p.last_sync_stats?.created ?? 0}</span>
                  <span>updated {p.last_sync_stats?.updated ?? 0}</span>
                  {p.last_sync_stats?.role_grants ? <span>roles {p.last_sync_stats.role_grants}</span> : null}
                  {p.last_sync_stats?.deactivated ? <span>deactivated {p.last_sync_stats.deactivated}</span> : null}
                  <span className="text-ink-500">{new Date(p.last_synced_at).toLocaleString()}</span>
                </>
              ) : <span className="text-ink-500">never synced</span>}
            </div>
            {Array.isArray(p.last_sync_stats?.errors) && p.last_sync_stats.errors.length > 0 && (
              <p className="text-[11px] text-danger-400 mt-2 flex items-center gap-1">
                <AlertTriangle className="size-3" /> {p.last_sync_stats.errors.slice(0, 2).join("; ")}
              </p>
            )}

            <div className="flex items-center gap-2 mt-4">
              <SyncButton id={p.id} />
              <TestButton id={p.id} />
              <button className="btn-secondary text-xs" onClick={() => setEditing(p)}>Edit</button>
              <button className="btn-secondary text-xs ml-auto" onClick={() => remove.mutate(p.id)}>
                <Trash2 className="size-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <ProviderModal
          existing={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => { qc.invalidateQueries({ queryKey: ["idp-providers"] }); setEditing(null); }}
        />
      )}
    </div>
  );
}

function SyncButton({ id }: { id: string }) {
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);
  const sync = useMutation({
    mutationFn: () => api.post<any>(`/api/v1/idp/providers/${id}/sync`),
    onSuccess: (d) => {
      const s = d.stats || {};
      setMsg(`+${s.created || 0} created, ${s.updated || 0} updated`);
      qc.invalidateQueries({ queryKey: ["idp-providers"] });
    },
    onError: () => setMsg("sync failed"),
  });
  return (
    <button className="btn-primary text-xs" disabled={sync.isPending} onClick={() => sync.mutate()}>
      <RefreshCw className={`size-3.5 ${sync.isPending ? "animate-spin" : ""}`} />
      {sync.isPending ? "Syncing…" : msg || "Sync now"}
    </button>
  );
}

function TestButton({ id }: { id: string }) {
  const [result, setResult] = useState<string | null>(null);
  const test = useMutation({
    mutationFn: () => api.post<any>(`/api/v1/idp/providers/${id}/test`),
    onSuccess: (d) => setResult(d.ok ? `✓ ${d.org || "connected"}` : "✓ connected"),
    onError: () => setResult("✗ failed"),
  });
  return (
    <button className="btn-secondary text-xs" disabled={test.isPending} onClick={() => test.mutate()}>
      <CheckCircle2 className="size-3.5" /> {test.isPending ? "Testing…" : result || "Test"}
    </button>
  );
}

function ProviderModal({ existing, onClose, onSaved }:
  { existing: Provider | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<any>(existing ? {
    name: existing.name, base_url: existing.base_url, api_token: "",
    sync_mode: existing.sync_mode, group_id: existing.group_id || "",
    default_mode: existing.default_mode,
    role_mapping_json: JSON.stringify(existing.role_mapping || {}, null, 2),
    default_on_behalf_user_id: existing.default_on_behalf_user_id || "",
    deactivate_missing: existing.deactivate_missing, is_enabled: existing.is_enabled,
  } : {
    name: "", base_url: "", api_token: "", sync_mode: "agents", group_id: "",
    default_mode: "human_supervised", role_mapping_json: "{}",
    default_on_behalf_user_id: "", deactivate_missing: false, is_enabled: true,
  });
  const [err, setErr] = useState<string | null>(null);

  const { data: members = [] } = useQuery({
    queryKey: ["org-members"], queryFn: () => api.get<any[]>("/api/v1/org/members"),
  });
  const { data: roles = [] } = useQuery({
    queryKey: ["roles"], queryFn: () => api.get<any[]>("/api/v1/roles"),
  });

  const save = useMutation({
    mutationFn: () => {
      let role_mapping: any = {};
      try { role_mapping = JSON.parse(form.role_mapping_json || "{}"); }
      catch { throw new Error("Role mapping is not valid JSON"); }
      const payload: any = {
        name: form.name, base_url: form.base_url, sync_mode: form.sync_mode,
        group_id: form.group_id || null, default_mode: form.default_mode, role_mapping,
        default_on_behalf_user_id: form.default_on_behalf_user_id || null,
        deactivate_missing: form.deactivate_missing, is_enabled: form.is_enabled,
      };
      if (form.api_token) payload.api_token = form.api_token;
      return existing
        ? api.patch(`/api/v1/idp/providers/${existing.id}`, payload)
        : api.post("/api/v1/idp/providers", { provider: "okta", ...payload });
    },
    onSuccess: onSaved,
    onError: (e: any) => setErr(e?.message || "Could not save"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(3px)" }} onClick={onClose}>
      <div className="w-full max-w-lg card p-6 max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div className="text-base font-semibold text-ink-50">{existing ? "Edit Okta connection" : "Connect Okta"}</div>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-50"><X className="size-5" /></button>
        </div>
        <div className="space-y-3">
          <Field label="Name">
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Acme Okta" />
          </Field>
          <Field label="Okta org URL">
            <input className="input font-mono" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://acme.okta.com" />
          </Field>
          <Field label={existing ? "API token (leave blank to keep current)" : "API token (SSWS)"}
                 hint="Create in Okta: Security → API → Tokens. Stored encrypted.">
            <input className="input font-mono" type="password" value={form.api_token}
              onChange={(e) => setForm({ ...form, api_token: e.target.value })}
              placeholder={existing?.has_token ? "•••••••• (unchanged)" : "00aBcD..."} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Sync mode">
              <select className="input" value={form.sync_mode} onChange={(e) => setForm({ ...form, sync_mode: e.target.value })}>
                <option value="agents">Okta agents (/api/v1/agents)</option>
                <option value="group">Okta group members</option>
              </select>
            </Field>
            <Field label="Default agent mode">
              <select className="input" value={form.default_mode} onChange={(e) => setForm({ ...form, default_mode: e.target.value })}>
                <option value="human_supervised">human_supervised</option>
                <option value="autonomous">autonomous</option>
                <option value="read_only">read_only</option>
              </select>
            </Field>
          </div>
          {form.sync_mode === "group" && (
            <Field label="Okta group ID" hint="Members of this group are imported as agents.">
              <input className="input font-mono" value={form.group_id} onChange={(e) => setForm({ ...form, group_id: e.target.value })} placeholder="00g1a2b3c4..." />
            </Field>
          )}
          <Field label="Role mapping (JSON)" hint={`Okta group name → Kynara role slug. Available roles: ${(roles as any[]).map(r => r.slug).join(", ") || "none"}`}>
            <textarea className="input font-mono text-xs min-h-[80px]" value={form.role_mapping_json}
              onChange={(e) => setForm({ ...form, role_mapping_json: e.target.value })}
              placeholder={'{\n  "AI Agents - CRM": "crm-reader"\n}'} />
          </Field>
          <Field label="Agents act on behalf of" hint="Required for role mapping to grant scopes.">
            <select className="input" value={form.default_on_behalf_user_id}
              onChange={(e) => setForm({ ...form, default_on_behalf_user_id: e.target.value })}>
              <option value="">— none (import only, no role grants) —</option>
              {(members as any[]).map((m) => (
                <option key={m.user_id} value={m.user_id}>{m.display_name || m.email}</option>
              ))}
            </select>
          </Field>
          <div className="flex items-center gap-4 pt-1">
            <label className="flex items-center gap-2 text-sm text-ink-200">
              <input type="checkbox" checked={form.deactivate_missing}
                onChange={(e) => setForm({ ...form, deactivate_missing: e.target.checked })} />
              Deactivate agents removed from Okta
            </label>
            <label className="flex items-center gap-2 text-sm text-ink-200">
              <input type="checkbox" checked={form.is_enabled}
                onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} />
              Enabled
            </label>
          </div>
          {err && <p className="text-[11px] text-danger-400 flex items-center gap-1"><AlertTriangle className="size-3" /> {err}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" disabled={save.isPending || !form.name || !form.base_url}
              onClick={() => { setErr(null); save.mutate(); }}>
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
