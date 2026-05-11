import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";
import {
  PlayCircle, Save, CheckCircle2, XCircle, AlertTriangle,
  ChevronDown, ChevronUp, Info, Plus, Trash2, Link2, X,
} from "lucide-react";

const DEFAULT_POLICY = {
  slug: "",
  display_name: "",
  description: "",
  effect: "allow",
  priority: 500,
  actions: [] as string[],
  resource_types: [] as string[],
  condition: {
    op: "and",
    args: [
      { op: "time_between", args: ["ctx.context.time", "09:00", "18:00"] },
    ],
  },
  is_enabled: true,
};

export default function PolicyEditorPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const isNew = !id || id === "new";
  const [bindingOpen, setBindingOpen] = useState(false);
  const [newSelector, setNewSelector] = useState("*");

  const { data: existing } = useQuery({
    queryKey: ["policy", id],
    queryFn: async () => (await api.get<any[]>("/api/v1/policies")).find((p) => p.id === id),
    enabled: !isNew,
  });

  const [form, setForm] = useState<any>(DEFAULT_POLICY);
  const [isDirty, setIsDirty] = useState(false);

  // Sync form when existing policy loads; validate condition immediately
  useEffect(() => {
    if (existing && !isDirty) {
      setForm(existing);
      setConditionError(validateConditionNode(existing.condition));
    }
  }, [existing]);

  function updateForm(patch: any) {
    setForm((f: any) => ({ ...f, ...patch }));
    setIsDirty(true);
  }

  // ── Condition validation ───────────────────────────────────────────────
  const [conditionError, setConditionError] = useState("");

  function validateConditionNode(node: any): string {
    if (node === null || node === undefined) return "";
    if (typeof node !== "object" || Array.isArray(node)) return "Condition must be a JSON object.";
    if (Object.keys(node).length === 0) return ""; // empty = match-all, valid
    if (!("op" in node))
      return `Missing "op" key. The condition must be a node like {"op":"and","args":[…]}, not a plain object like ${JSON.stringify(node).slice(0,60)}.`;
    const validOps = ["and","or","not","eq","neq","gt","gte","lt","lte","in","contains","starts_with","time_between","has_scope"];
    if (!validOps.includes(node.op))
      return `Unknown op "${node.op}". Valid ops: ${validOps.join(", ")}.`;
    return "";
  }

  // ── Simulator state ────────────────────────────────────────────────────
  const [simSubjectType, setSimSubjectType] = useState("agent");
  const [simSubjectId, setSimSubjectId]     = useState("");
  const [simAction, setSimAction]   = useState("crm.contacts.read");
  const [simResource, setSimResource] = useState("crm.contact:c_demo");
  const [simContext, setSimContext]  = useState<string>(
    JSON.stringify({ ip_country: "US", time: "10:00" }, null, 2)
  );
  const [simResult, setSimResult]   = useState<any>(null);
  const [showCtx, setShowCtx]       = useState(false);

  const { data: simAgents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<any[]>("/api/v1/agents"),
  });
  const { data: simMembers = [] } = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<any[]>("/api/v1/org/members"),
  });
  const { data: simApiKeys = [] } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<any[]>("/api/v1/api-keys"),
  });

  const { data: bindings = [], refetch: refetchBindings } = useQuery({
    queryKey: ["policy-bindings", id],
    queryFn: () => api.get<any[]>(`/api/v1/policies/${id}/bindings`),
    enabled: !isNew && !!id,
  });

  const addBinding = useMutation({
    mutationFn: () => api.post(`/api/v1/policies/${id}/bindings`, { subject_selector: newSelector }),
    onSuccess: () => { refetchBindings(); setBindingOpen(false); setNewSelector("*"); },
  });

  const removeBinding = useMutation({
    mutationFn: (bindingId: string) => api.del(`/api/v1/policies/${id}/bindings/${bindingId}`),
    onSuccess: () => refetchBindings(),
  });

  const save = useMutation({
    mutationFn: () =>
      isNew ? api.post("/api/v1/policies", form) : api.put(`/api/v1/policies/${id}`, form),
    onSuccess: () => { setIsDirty(false); nav("/app/policies"); },
  });

  const simulate = useMutation({
    mutationFn: async () => {
      let ctx: Record<string, unknown> = {};
      try { ctx = JSON.parse(simContext); } catch { /* ignore */ }

      const [resType, resId] = simResource.split(":").concat([""]);
      return api.post<any>("/api/v1/decisions/check", {
        subject_type: simSubjectType,
        subject_id:   simSubjectId,
        action: simAction,
        resource: { type: resType || null, id: resId || null, attrs: {} },
        context: ctx,
      });
    },
    onSuccess: (d) => setSimResult(d),
  });

  const effectColor = {
    allow:            { text: "#34D399", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.25)" },
    deny:             { text: "#F87171", bg: "rgba(244,63,94,0.1)",  border: "rgba(190,18,60,0.25)" },
    require_approval: { text: "#FBBF24", bg: "rgba(245,158,11,0.1)", border: "rgba(180,83,9,0.3)" },
  } as Record<string, any>;

  const EffectIcon = simResult?.effect === "allow"
    ? CheckCircle2 : simResult?.effect === "deny"
    ? XCircle : AlertTriangle;

  return (
    <div>
      <PageHeader
        title={isNew ? "New policy" : `Edit · ${form.display_name || id}`}
        subtitle="Policies are matched in priority order; first terminal effect wins. Fail-closed by default."
        actions={
          <button
            onClick={() => save.mutate()}
            className="btn-primary"
            disabled={save.isPending || !!conditionError}
          >
            <Save className="size-4" />
            {save.isPending ? "Saving…" : isDirty ? "Save changes" : "Save"}
          </button>
        }
      />
      <div className="px-8 py-6 grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Left: policy fields ───────────────────────────── */}
        <div className="card p-5 space-y-3">
          <Field label="Slug">
            <input className="input font-mono"
                   value={form.slug}
                   onChange={(e) => updateForm({ slug: e.target.value })} />
          </Field>
          <Field label="Display name">
            <input className="input" value={form.display_name}
                   onChange={(e) => updateForm({ display_name: e.target.value })} />
          </Field>
          <Field label="Description">
            <textarea className="input min-h-[72px]" value={form.description || ""}
                      onChange={(e) => updateForm({ description: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Effect">
              <select className="input" value={form.effect}
                      onChange={(e) => updateForm({ effect: e.target.value })}>
                <option value="allow">allow</option>
                <option value="deny">deny</option>
                <option value="require_approval">require_approval</option>
              </select>
            </Field>
            <Field label="Priority">
              <input type="number" className="input font-mono" value={form.priority}
                     onChange={(e) => updateForm({ priority: +e.target.value })} />
            </Field>
          </div>
          <Field label="Scopes (comma-separated, supports globs)">
            <input className="input font-mono"
                   value={(form.actions || []).join(",")}
                   onChange={(e) => updateForm({
                     actions: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean),
                   })} />
          </Field>
          <Field label="Resource types (comma-separated)">
            <input className="input font-mono"
                   value={(form.resource_types || []).join(",")}
                   onChange={(e) => updateForm({
                     resource_types: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean),
                   })} />
          </Field>
          <Field label="Condition (JSON AST)">
            <textarea
              className={`input font-mono text-xs min-h-[220px] ${conditionError ? "border-danger-500" : ""}`}
              value={JSON.stringify(form.condition || {}, null, 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  updateForm({ condition: parsed });
                  setConditionError(validateConditionNode(parsed));
                } catch {
                  setConditionError("Invalid JSON — fix syntax before saving.");
                }
              }}
            />
            {conditionError && (
              <p className="text-[11px] text-danger-400 mt-1 leading-snug">{conditionError}</p>
            )}
            <p className="text-[10px] text-ink-500 mt-1">
              Use <span className="font-mono">{"{ }"}</span> (empty object) to match all requests.
              Needs <span className="font-mono">"op"</span> + <span className="font-mono">"args"</span> for conditions.
            </p>
          </Field>

          {/* Enabled toggle */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-ink-300">Policy enabled</span>
            <button
              type="button"
              onClick={() => updateForm({ is_enabled: !form.is_enabled })}
              className={`relative w-10 h-5 rounded-full transition ${form.is_enabled ? "bg-accent-500" : "bg-ink-700"}`}
            >
              <span className={`absolute top-0.5 size-4 rounded-full bg-white transition-all ${form.is_enabled ? "left-5" : "left-0.5"}`} />
            </button>
          </div>
        </div>

        {/* ── Right: simulator ──────────────────────────────── */}
        <div className="space-y-4">
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-1">
              <PlayCircle className="size-4 text-accent-500" />
              <span className="text-sm font-medium">Simulate</span>
            </div>
            <p className="text-xs text-ink-400 mb-4">
              Test a decision request against the currently <strong className="text-ink-200">saved</strong> policy set.
              Save your changes first to include them in the simulation.
            </p>

            {isDirty && (
              <div className="rounded-lg px-3 py-2 text-xs text-warn-300 flex items-center gap-2 mb-4"
                style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
                <AlertTriangle className="size-3.5 shrink-0" />
                You have unsaved changes — save first so the simulator picks them up.
              </div>
            )}

            <div className="space-y-3">
              <Field label="Subject">
                <div className="flex gap-2">
                  <select
                    className="input w-32 shrink-0"
                    value={simSubjectType}
                    onChange={(e) => { setSimSubjectType(e.target.value); setSimSubjectId(""); setSimResult(null); }}
                  >
                    <option value="agent">agent</option>
                    <option value="user">user</option>
                    <option value="api_key">api_key</option>
                  </select>
                  {simSubjectType === "agent" ? (
                    <select className="input flex-1" value={simSubjectId}
                      onChange={(e) => { setSimSubjectId(e.target.value); setSimResult(null); }}>
                      <option value="">— select agent —</option>
                      {(simAgents as any[]).map((a: any) => (
                        <option key={a.id} value={a.id}>{a.display_name} ({a.slug})</option>
                      ))}
                    </select>
                  ) : simSubjectType === "user" ? (
                    <select className="input flex-1" value={simSubjectId}
                      onChange={(e) => { setSimSubjectId(e.target.value); setSimResult(null); }}>
                      <option value="">— select user —</option>
                      {(simMembers as any[]).map((m: any) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.display_name || m.email} ({m.seat_role})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <select className="input flex-1" value={simSubjectId}
                      onChange={(e) => { setSimSubjectId(e.target.value); setSimResult(null); }}>
                      <option value="">— select API key —</option>
                      {(simApiKeys as any[]).map((k: any) => (
                        <option key={k.id} value={k.id}>{k.name} ({k.prefix}…{k.last_four})</option>
                      ))}
                    </select>
                  )}
                </div>
              </Field>
              <Field label="Scope">
                <input className="input font-mono" value={simAction}
                       onChange={(e) => { setSimAction(e.target.value); setSimResult(null); }} />
              </Field>
              <Field label="Resource (type:id)">
                <input className="input font-mono" value={simResource}
                       onChange={(e) => { setSimResource(e.target.value); setSimResult(null); }} />
              </Field>

              {/* Collapsible context */}
              <div>
                <button
                  type="button"
                  onClick={() => setShowCtx(v => !v)}
                  className="flex items-center gap-1.5 text-xs text-ink-400 hover:text-ink-200 transition-colors mb-1"
                >
                  {showCtx ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                  Context (JSON)
                </button>
                {showCtx && (
                  <textarea
                    className="input font-mono text-xs min-h-[96px]"
                    value={simContext}
                    onChange={(e) => { setSimContext(e.target.value); setSimResult(null); }}
                  />
                )}
              </div>
            </div>

            <button
              className="btn-primary mt-4 w-full justify-center"
              onClick={() => simulate.mutate()}
              disabled={simulate.isPending || !simSubjectId || !simAction}
            >
              <PlayCircle className="size-4" />
              {simulate.isPending ? "Evaluating…" : "Run simulation"}
            </button>

            {simulate.isError && (
              <div className="mt-3 rounded-lg px-3 py-2 text-xs text-danger-400"
                style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(190,18,60,0.25)" }}>
                Simulation failed — check the API is reachable and your context JSON is valid.
              </div>
            )}
          </div>

          {/* ── Result card ── */}
          {simResult && (() => {
            const e = simResult.effect as string;
            const col = effectColor[e] ?? effectColor.deny;
            return (
              <div className="card p-5 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: col.bg, border: `1px solid ${col.border}` }}>
                    <EffectIcon className="size-5" style={{ color: col.text }} />
                  </div>
                  <div>
                    <div className="text-base font-bold" style={{ color: col.text }}>
                      {e.replace("_", " ").toUpperCase()}
                    </div>
                    <div className="text-xs text-ink-400 mt-0.5">
                      {simResult.matched_policy_id
                        ? <>Matched policy <code className="font-mono text-ink-200">{simResult.matched_policy_id}</code></>
                        : "No policy matched — fail-closed default applied"}
                    </div>
                  </div>
                </div>

                {simResult.matched_policy_id && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {[
                      ["Policy ID", simResult.matched_policy_id],
                      ["Effect", simResult.effect],
                      ["Latency", simResult.latency_ms != null ? `${simResult.latency_ms}ms` : "—"],
                      ["Decision ID", simResult.decision_id ?? "—"],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-lg px-3 py-2"
                        style={{ background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.08)" }}>
                        <div className="text-ink-500 mb-0.5">{k}</div>
                        <div className="font-mono text-ink-100 truncate">{v}</div>
                      </div>
                    ))}
                  </div>
                )}

                <details className="group">
                  <summary className="flex items-center gap-1.5 text-xs text-ink-400 hover:text-ink-200 cursor-pointer select-none transition-colors">
                    <Info className="size-3.5" /> Full response
                  </summary>
                  <pre className="mt-2 bg-ink-900 border border-ink-800 rounded-lg p-3 text-xs overflow-x-auto text-ink-200">
{JSON.stringify(simResult, null, 2)}
                  </pre>
                </details>
              </div>
            );
          })()}
        </div>
      </div>

      {/* ── Bindings ── */}
      {!isNew && (
        <div className="px-8 pb-8">
          <div className="card p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Link2 className="size-4 text-accent-500" />
                <span className="font-medium text-sm">Bindings</span>
                <span className="text-xs text-ink-500">
                  — subjects this policy is enforced on (<code className="font-mono text-[10px]">*</code> = all agents,{" "}
                  <code className="font-mono text-[10px]">agent:&lt;id&gt;</code> = one agent)
                </span>
              </div>
              <button className="btn-primary text-xs" onClick={() => setBindingOpen(true)}>
                <Plus className="size-3" /> Add binding
              </button>
            </div>

            {bindings.length > 0 ? (
              <table className="table">
                <thead>
                  <tr><th>Subject selector</th><th>Created</th><th></th></tr>
                </thead>
                <tbody>
                  {bindings.map((b: any) => (
                    <tr key={b.id}>
                      <td>
                        <code className="font-mono text-sm text-accent-400">{b.subject_selector}</code>
                      </td>
                      <td className="text-xs text-ink-400">
                        {b.created_at ? new Date(b.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td>
                        <button
                          className="text-ink-500 hover:text-danger-400 transition-colors p-1"
                          title="Remove binding"
                          onClick={() => removeBinding.mutate(b.id)}
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-center py-8">
                <Link2 className="size-8 mx-auto mb-3 text-ink-700" />
                <p className="text-sm text-ink-400 mb-1">No bindings yet — this policy won't be enforced.</p>
                <p className="text-xs text-ink-600 mb-4">
                  Add a binding with selector <code className="font-mono text-[10px]">*</code> to apply to all agents,
                  or <code className="font-mono text-[10px]">agent:&lt;id&gt;</code> for a specific agent.
                </p>
                <button className="btn-primary text-xs" onClick={() => setBindingOpen(true)}>
                  <Plus className="size-3" /> Add first binding
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Add binding modal ── */}
      {bindingOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-md rounded-2xl shadow-2xl"
            style={{ background: "#0D1421", border: "1px solid rgba(148,163,184,0.12)" }}>
            <div className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <div className="text-base font-semibold text-white">Add binding</div>
              <button onClick={() => setBindingOpen(false)} className="text-ink-400 hover:text-white">
                <X className="size-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-3">
              <label className="label">Subject selector</label>
              <input
                className="input font-mono"
                value={newSelector}
                onChange={e => setNewSelector(e.target.value)}
                placeholder="* or agent:<agent-id>"
              />
              <div className="text-xs text-ink-500 space-y-1">
                <p><code className="font-mono">*</code> — applies to all agents in this org</p>
                <p><code className="font-mono">agent:&lt;id&gt;</code> — applies to one specific agent</p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4"
              style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
              <button className="btn-ghost" onClick={() => setBindingOpen(false)}>Cancel</button>
              <button className="btn-primary" disabled={!newSelector || addBinding.isPending}
                onClick={() => addBinding.mutate()}>
                {addBinding.isPending ? "Adding…" : "Add binding"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}
