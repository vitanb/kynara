import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck, Plus, X, Pencil, Trash2, Tag,
  Search, ChevronDown, ChevronUp, AlertTriangle,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

const defaultForm = {
  slug: "",
  display_name: "",
  description: "",
};

type ModalMode = "create" | "edit";

const RISK_COLORS: Record<string, string> = {
  low:      "bg-ok-500/10 text-ok-400 border-ok-500/20",
  medium:   "bg-warn-500/10 text-warn-400 border-warn-500/20",
  high:     "bg-orange-500/10 text-orange-400 border-orange-500/20",
  critical: "bg-danger-500/10 text-danger-400 border-danger-500/20",
};

function RiskBadge({ risk }: { risk: string }) {
  return (
    <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded border ${RISK_COLORS[risk] ?? RISK_COLORS.low}`}>
      {risk}
    </span>
  );
}

export default function RolesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ModalMode>("create");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [customScope, setCustomScope] = useState("");
  const [scopeSearch, setScopeSearch] = useState("");
  const [catalogOpen, setCatalogOpen] = useState(true);
  const [error, setError] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data: roles = [] } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<any[]>("/api/v1/roles"),
  });

  // Fetch the scope catalog — only when modal is open
  const { data: catalogTools = [] } = useQuery({
    queryKey: ["tools-catalog"],
    queryFn: () => api.get<any[]>("/api/v1/tools"),
    enabled: open,
  });

  // Flatten tools → individual scope entries with parent tool metadata
  const catalogEntries = useMemo(() => {
    const entries: { scope: string; toolName: string; description: string; risk: string }[] = [];
    for (const t of catalogTools as any[]) {
      for (const s of (t.scopes || []) as string[]) {
        entries.push({
          scope: s,
          toolName: `${t.namespace}.${t.name}`,
          description: t.description || "",
          risk: t.risk_class || "low",
        });
      }
    }
    return entries;
  }, [catalogTools]);

  const filteredEntries = useMemo(() => {
    const q = scopeSearch.toLowerCase();
    return catalogEntries.filter(
      e => !q || e.scope.toLowerCase().includes(q) || e.toolName.toLowerCase().includes(q)
    );
  }, [catalogEntries, scopeSearch]);

  const create = useMutation({
    mutationFn: () => api.post("/api/v1/roles", {
      slug: form.slug.trim(),
      display_name: form.display_name.trim(),
      description: (form as any).description?.trim() || null,
      scopes: selectedScopes,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["roles"] }); closeModal(); },
    onError: (e: any) => setError(e?.message ?? "Failed to create role"),
  });

  const update = useMutation({
    mutationFn: () => api.put(`/api/v1/roles/${editingId}`, {
      display_name: form.display_name.trim(),
      description: (form as any).description?.trim() || null,
      scopes: selectedScopes,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["roles"] }); closeModal(); },
    onError: (e: any) => setError(e?.message ?? "Failed to update role"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/roles/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["roles"] }); setDeleteConfirm(null); },
    onError: (e: any) => setError(e?.message ?? "Failed to delete role"),
  });

  function toggleScope(s: string) {
    setSelectedScopes(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    );
  }

  function addCustomScope() {
    const s = customScope.trim();
    if (s && !selectedScopes.includes(s)) {
      setSelectedScopes(prev => [...prev, s]);
    }
    setCustomScope("");
  }

  function setField(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const val = e.target.value;
      setForm(f => {
        const next = { ...f, [k]: val };
        if (k === "display_name" && mode === "create") {
          (next as any).slug = val.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
        }
        return next;
      });
    };
  }

  function openCreate() {
    setMode("create");
    setForm(defaultForm);
    setSelectedScopes([]);
    setCustomScope("");
    setScopeSearch("");
    setCatalogOpen(true);
    setError("");
    setEditingId(null);
    setOpen(true);
  }

  function openEdit(r: any) {
    setMode("edit");
    setEditingId(r.id);
    setForm({
      slug: r.slug,
      display_name: r.display_name,
      description: r.description || "",
    });
    setSelectedScopes(r.scopes || []);
    setCustomScope("");
    setScopeSearch("");
    setCatalogOpen(true);
    setError("");
    setOpen(true);
  }

  function closeModal() {
    setOpen(false);
    setError("");
    setEditingId(null);
    setSelectedScopes([]);
  }

  const isPending = create.isPending || update.isPending;

  return (
    <div>
      <PageHeader
        title="Roles"
        subtitle="Named sets of scopes you can assign to agents. An agent's granted scopes are the union of all its active role assignments."
      />
      <div className="px-8 py-6 space-y-6">
        <div className="flex justify-end">
          <button className="btn-primary" onClick={openCreate}>
            <Plus className="size-4" /> New Role
          </button>
        </div>

        {/* Role table */}
        {(roles as any[]).length === 0 ? (
          <div className="card p-8 text-center text-ink-400">
            No roles yet.{" "}
            <button className="text-accent-400 underline" onClick={openCreate}>
              Create your first role
            </button>{" "}
            — roles define which scopes an agent is allowed to request.
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Slug</th>
                  <th>Scopes granted</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(roles as any[]).map((r: any) => (
                  <tr key={r.id}>
                    <td>
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="size-4 text-accent-400 shrink-0" />
                        <div>
                          <div className="text-sm font-medium">{r.display_name}</div>
                          {r.description && (
                            <div className="text-xs text-ink-400">{r.description}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="font-mono text-xs text-ink-300">{r.slug}</span>
                      {r.is_system && (
                        <span className="ml-2 pill text-[9px]">system</span>
                      )}
                    </td>
                    <td>
                      {(r.scopes || []).length === 0 ? (
                        <span className="text-xs text-ink-500">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {(r.scopes as string[]).map((s: string) => (
                            <span key={s} className="flex items-center gap-1 pill font-mono text-[10px]">
                              <Tag className="size-2.5" />{s}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="flex items-center gap-2 justify-end">
                        {!r.is_system && (
                          <>
                            <button className="btn-ghost text-xs" onClick={() => openEdit(r)}>
                              <Pencil className="size-3.5" /> Edit
                            </button>
                            <button
                              className="btn-ghost text-xs text-danger-400 hover:text-danger-300"
                              onClick={() => setDeleteConfirm(r.id)}
                            >
                              <Trash2 className="size-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Explainer */}
        <div className="card p-4 text-xs text-ink-400 space-y-1">
          <p className="font-medium text-ink-300">How scopes flow to agents</p>
          <p>1. Create a role here — pick scopes from the Scope Catalog or type custom ones.</p>
          <p>2. Go to an Agent → Assignments → Add Assignment — pick a user and select this role.</p>
          <p>3. In the Decisions simulator, pick the agent. Leave "on behalf of" as <em>autonomous</em> to union all assignment role scopes, or pick a specific user to intersect with their scopes.</p>
          <p>4. The action must also be covered by an <strong>allow</strong> policy bound to the agent or <code className="font-mono">*</code>.</p>
        </div>
      </div>

      {/* Delete confirm */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-page-dark border border-ink-800 rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6 space-y-4">
            <p className="text-sm text-ink-200">
              Delete this role? Any agent assignments using it will lose these scopes.
            </p>
            <div className="flex justify-end gap-3">
              <button className="btn-ghost" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button
                className="btn-primary bg-danger-600 hover:bg-danger-500"
                onClick={() => remove.mutate(deleteConfirm!)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit modal */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-page-dark border border-ink-800 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-ink-800 shrink-0">
              <h2 className="text-base font-semibold text-white">
                {mode === "edit" ? "Edit Role" : "New Role"}
              </h2>
              <button onClick={closeModal} className="text-ink-400 hover:text-white">
                <X className="size-5" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5">

              {/* Name + slug + description */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Display name <span className="text-danger-400">*</span></label>
                  <input
                    className="input"
                    placeholder="e.g. Payments Agent"
                    value={form.display_name}
                    onChange={setField("display_name")}
                    autoFocus
                  />
                </div>
                <div>
                  <label className="label">
                    Slug <span className="text-danger-400">*</span>
                    {mode === "edit" && <span className="text-ink-500 font-normal ml-1">(locked)</span>}
                  </label>
                  <input
                    className="input font-mono text-sm"
                    placeholder="payments-agent"
                    value={form.slug}
                    onChange={setField("slug")}
                    disabled={mode === "edit"}
                  />
                </div>
              </div>

              <div>
                <label className="label">Description</label>
                <input
                  className="input"
                  placeholder="What can agents with this role do?"
                  value={(form as any).description}
                  onChange={setField("description" as any)}
                />
              </div>

              {/* ── Scope picker ── */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="label mb-0">Scopes granted</label>
                  <span className="text-[10px] text-ink-500">
                    {selectedScopes.length} selected
                  </span>
                </div>

                {/* Selected chips */}
                {selectedScopes.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-3 p-2.5 bg-ink-900 rounded-lg border border-ink-800">
                    {selectedScopes.map(s => (
                      <span
                        key={s}
                        className="flex items-center gap-1 bg-accent-500/15 text-accent-300 border border-accent-500/25 rounded px-2 py-0.5 text-[11px] font-mono"
                      >
                        {s}
                        <button
                          type="button"
                          onClick={() => toggleScope(s)}
                          className="text-accent-400 hover:text-white ml-0.5"
                        >
                          <X className="size-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Catalog picker */}
                <div className="border border-ink-800 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2.5 bg-ink-900 text-xs text-ink-300 hover:text-white transition-colors"
                    onClick={() => setCatalogOpen(v => !v)}
                  >
                    <span className="font-medium">Browse Scope Catalog</span>
                    {catalogOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                  </button>

                  {catalogOpen && (
                    <div>
                      <div className="px-3 py-2 border-t border-ink-800 bg-ink-950">
                        <div className="flex items-center gap-2 bg-ink-900 rounded px-2 py-1.5">
                          <Search className="size-3.5 text-ink-500 shrink-0" />
                          <input
                            className="bg-transparent text-xs text-ink-200 placeholder-ink-500 outline-none flex-1 min-w-0"
                            placeholder="Search scopes or tool names…"
                            value={scopeSearch}
                            onChange={e => setScopeSearch(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="max-h-52 overflow-y-auto divide-y divide-ink-800/50">
                        {filteredEntries.length === 0 ? (
                          <div className="px-3 py-6 text-center text-xs text-ink-500">
                            {catalogEntries.length === 0
                              ? "No scopes registered yet — add entries in the Scope Catalog first."
                              : "No matches."}
                          </div>
                        ) : (
                          filteredEntries.map(e => {
                            const checked = selectedScopes.includes(e.scope);
                            return (
                              <button
                                key={e.scope}
                                type="button"
                                onClick={() => toggleScope(e.scope)}
                                className={`w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-ink-800/50 transition-colors ${checked ? "bg-accent-500/5" : ""}`}
                              >
                                {/* Checkbox */}
                                <div className={`mt-0.5 size-3.5 rounded border shrink-0 flex items-center justify-center ${checked ? "bg-accent-500 border-accent-500" : "border-ink-600"}`}>
                                  {checked && <span className="text-white text-[8px] font-bold leading-none">✓</span>}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-mono text-xs text-ink-200">{e.scope}</span>
                                    <RiskBadge risk={e.risk} />
                                  </div>
                                  <div className="text-[10px] text-ink-500 mt-0.5 truncate">
                                    {e.toolName}{e.description ? ` — ${e.description}` : ""}
                                  </div>
                                </div>
                              </button>
                            );
                          })
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Custom scope free-type */}
                <div className="mt-2">
                  <div className="flex gap-2">
                    <input
                      className="input font-mono text-xs flex-1"
                      placeholder="Add custom scope e.g. payments.* or my.custom.action"
                      value={customScope}
                      onChange={e => setCustomScope(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addCustomScope(); } }}
                    />
                    <button
                      type="button"
                      className="btn-ghost text-xs shrink-0"
                      onClick={addCustomScope}
                      disabled={!customScope.trim()}
                    >
                      <Plus className="size-3.5" /> Add
                    </button>
                  </div>
                  <p className="text-[10px] text-ink-500 mt-1">
                    Use <code className="font-mono">*</code> for full access or <code className="font-mono">payments.*</code> for a namespace wildcard.
                    Wildcards match any scope starting with that prefix at decision time.
                  </p>
                </div>

                {selectedScopes.length === 0 && (
                  <div className="flex items-start gap-2 mt-2 text-[11px] text-warn-400 bg-warn-500/5 border border-warn-500/15 rounded-lg px-3 py-2">
                    <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
                    No scopes selected — agents with this role will be denied by the RBAC gate for every action.
                  </div>
                )}
              </div>

              {error && <p className="text-danger-400 text-xs">{error}</p>}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-ink-800 shrink-0">
              <button className="btn-ghost" onClick={closeModal}>Cancel</button>
              <button
                className="btn-primary"
                disabled={!form.display_name || !form.slug || isPending}
                onClick={() => mode === "edit" ? update.mutate() : create.mutate()}
              >
                {isPending ? "Saving…" : mode === "edit" ? "Save changes" : "Create Role"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
