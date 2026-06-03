import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Wrench, AlertTriangle, Plus, X, Pencil, BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

const RISK_CLASSES = ["low", "medium", "high", "critical"] as const;

const defaultForm = {
  namespace: "",
  name: "",
  description: "",
  risk_class: "low" as string,
  input_schema: '{\n  "type": "object",\n  "properties": {}\n}',
  scopes: "",
};

type ModalMode = "create" | "edit";

export default function ToolsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ModalMode>("create");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState("");
  const [schemaError, setSchemaError] = useState("");

  const { data = [] } = useQuery({
    queryKey: ["tools"],
    queryFn: () => api.get<any[]>("/api/v1/tools"),
  });

  const create = useMutation({
    mutationFn: () => {
      let parsed: any;
      try { parsed = JSON.parse(form.input_schema); }
      catch { throw new Error("Input schema is not valid JSON"); }
      const scopeList = form.scopes.split(/[\n,]+/).map((s: string) => s.trim()).filter(Boolean);
      return api.post("/api/v1/tools", {
        namespace: form.namespace.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
        risk_class: form.risk_class,
        input_schema: parsed,
        scopes: scopeList,
      });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tools"] }); closeModal(); },
    onError: (err: unknown) => setError((err as any)?.message ?? "Failed to create tool"),
  });

  const update = useMutation({
    mutationFn: () => {
      let parsed: any;
      try { parsed = JSON.parse(form.input_schema); }
      catch { throw new Error("Input schema is not valid JSON"); }
      const scopeList = form.scopes.split(/[\n,]+/).map((s: string) => s.trim()).filter(Boolean);
      return api.put(`/api/v1/tools/${editingId}`, {
        description: form.description.trim() || null,
        risk_class: form.risk_class,
        input_schema: parsed,
        scopes: scopeList,
        is_enabled: true,
      });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["tools"] }); closeModal(); },
    onError: (err: unknown) => setError((err as any)?.message ?? "Failed to update tool"),
  });

  function setField(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm(f => ({ ...f, [k]: e.target.value }));
      if (k === "input_schema") {
        try { JSON.parse(e.target.value); setSchemaError(""); }
        catch { setSchemaError("Invalid JSON"); }
      }
    };
  }

  function openCreate() {
    setMode("create");
    setForm(defaultForm);
    setError(""); setSchemaError(""); setEditingId(null);
    setOpen(true);
  }

  function openEdit(t: any) {
    setMode("edit");
    setEditingId(t.id);
    setForm({
      namespace: t.namespace,
      name: t.name,
      description: t.description || "",
      risk_class: t.risk_class,
      input_schema: JSON.stringify(t.input_schema ?? {}, null, 2),
      scopes: (t.scopes || []).join("\n"),
    });
    setError(""); setSchemaError("");
    setOpen(true);
  }

  function closeModal() {
    setOpen(false); setError(""); setSchemaError(""); setEditingId(null);
  }

  const groups: Record<string, any[]> = {};
  for (const t of data) (groups[t.namespace] ||= []).push(t);

  const isPending = create.isPending || update.isPending;

  return (
    <div>
      <PageHeader
        title="Scope Catalog"
        subtitle="Registry of callable actions agents may invoke. Each entry defines a scope string, risk level, and parameters. Add scopes to Roles to grant agents access."
      />
      <div className="px-8 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <Link
            to="/app/catalog"
            className="flex items-center gap-1.5 text-sm font-medium transition-colors"
            style={{ color: "var(--s0-accent-text)" }}
          >
            <BookOpen className="size-4" /> Browse Library
          </Link>
          <button className="btn-primary" onClick={openCreate}>
            <Plus className="size-4" /> New Tool
          </button>
        </div>

        {Object.entries(groups).map(([ns, tools]) => (
          <div key={ns}>
            <div className="text-xs uppercase tracking-wide text-ink-400 mb-2">{ns}</div>
            <div className="card overflow-hidden">
              <table className="table">
                <thead>
                  <tr>
                    <th>Tool</th><th>Risk</th><th>Required scopes</th><th>Enabled</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <Wrench className="size-4 text-ink-500" />
                          <div>
                            <div className="text-sm font-medium">{t.name}</div>
                            <div className="text-xs text-ink-400">{t.description || "—"}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={
                          t.risk_class === "critical" ? "pill-danger" :
                          t.risk_class === "high"     ? "pill-warn"   :
                          t.risk_class === "medium"   ? "pill-info"   : "pill-ok"
                        }>
                          {t.risk_class === "critical" && <AlertTriangle className="size-3" />} {t.risk_class}
                        </span>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {(t.scopes || []).map((s: string) => (
                            <span key={s} className="pill font-mono text-[10px]">{s}</span>
                          ))}
                        </div>
                      </td>
                      <td>
                        {t.is_enabled
                          ? <span className="pill-ok">enabled</span>
                          : <span className="pill-danger">disabled</span>}
                      </td>
                      <td>
                        <button
                          className="btn-ghost text-xs"
                          title="Edit tool"
                          onClick={() => openEdit(t)}
                        >
                          <Pencil className="size-3.5" /> Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}

        {!data.length && (
          <div className="card p-8 text-center text-ink-400">
            No tools registered yet.{" "}
            <button className="text-accent-400 underline" onClick={openCreate}>Add your first tool</button>
          </div>
        )}
      </div>

      {/* ── Create / Edit Modal ── */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-page-dark border border-ink-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-ink-800">
              <h2 className="text-base font-semibold text-ink-50">
                {mode === "edit" ? "Edit Tool" : "New Tool"}
              </h2>
              <button onClick={closeModal} className="text-ink-400 hover:text-ink-50">
                <X className="size-5" />
              </button>
            </div>

            <div className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Namespace <span className="text-danger-400">*</span></label>
                  <input
                    className="input"
                    placeholder="e.g. payments"
                    value={form.namespace}
                    onChange={setField("namespace")}
                    disabled={mode === "edit"}
                  />
                  {mode === "edit" && (
                    <p className="text-[10px] text-ink-500 mt-1">Namespace cannot be changed</p>
                  )}
                </div>
                <div>
                  <label className="label">Name <span className="text-danger-400">*</span></label>
                  <input
                    className="input"
                    placeholder="e.g. refund.issue"
                    value={form.name}
                    onChange={setField("name")}
                    disabled={mode === "edit"}
                  />
                  {mode === "edit" && (
                    <p className="text-[10px] text-ink-500 mt-1">Name cannot be changed</p>
                  )}
                </div>
              </div>

              <div>
                <label className="label">Description</label>
                <input className="input" placeholder="What does this tool do?" value={form.description} onChange={setField("description")} />
              </div>

              <div>
                <label className="label">Risk class <span className="text-danger-400">*</span></label>
                <select className="input" value={form.risk_class} onChange={setField("risk_class")}>
                  {RISK_CLASSES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              <div>
                <label className="label">
                  Required scopes
                  <span className="text-ink-500 font-normal ml-1">(one per line or comma-separated)</span>
                </label>
                <textarea
                  className="input font-mono text-xs"
                  rows={2}
                  placeholder={"payments.refund.issue\npayments.read"}
                  value={form.scopes}
                  onChange={setField("scopes")}
                />
              </div>

              <div>
                <label className="label">
                  Input schema
                  <span className="text-ink-500 font-normal ml-1">(JSON Schema)</span>
                  {schemaError && <span className="ml-2 text-danger-400 text-[10px]">{schemaError}</span>}
                </label>
                <textarea
                  className={`input font-mono text-xs ${schemaError ? "border-danger-500" : ""}`}
                  rows={6}
                  value={form.input_schema}
                  onChange={setField("input_schema")}
                  spellCheck={false}
                />
              </div>

              {error && <p className="text-danger-400 text-xs">{error}</p>}
            </div>

            <div className="flex justify-end gap-3 px-6 py-4 border-t border-ink-800">
              <button className="btn-ghost" onClick={closeModal}>Cancel</button>
              <button
                className="btn-primary"
                onClick={() => mode === "edit" ? update.mutate() : create.mutate()}
                disabled={!form.namespace || !form.name || !!schemaError || isPending}
              >
                {isPending ? "Saving…" : mode === "edit" ? "Save changes" : "Create Tool"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
