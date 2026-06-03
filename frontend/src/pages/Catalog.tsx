import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, ChevronDown, ChevronRight, Copy, Layers, BookOpen,
  Wrench, X, Plus, AlertTriangle, ExternalLink,
} from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── Risk colours ──────────────────────────────────────────────────────────────
const RISK: Record<string, { bg: string; text: string }> = {
  low:      { bg: "rgba(16,185,129,0.12)",  text: "#34D399" },
  medium:   { bg: "rgba(245,158,11,0.12)",  text: "#FBBF24" },
  high:     { bg: "rgba(244,63,94,0.12)",   text: "#F87171" },
  critical: { bg: "var(--s0-accent-subtle)",  text: "var(--s0-text-muted)" },
};

const EFFECT: Record<string, { bg: string; text: string }> = {
  allow:            { bg: "rgba(16,185,129,0.12)",  text: "#34D399" },
  deny:             { bg: "rgba(244,63,94,0.12)",   text: "#F87171" },
  require_approval: { bg: "rgba(245,158,11,0.12)",  text: "#FBBF24" },
};

const RISK_CLASSES = ["low", "medium", "high", "critical"] as const;

// ── Helpers ────────────────────────────────────────────────────────────────────
function copyText(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => { copyText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded transition-colors"
      style={{ background: "var(--s0-accent-subtle)", color: copied ? "#34D399" : "var(--s0-accent-text)", border: "1px solid var(--s0-accent-ring)" }}
    >
      {copied ? <CheckCircle2 className="size-3" /> : <Copy className="size-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ── Scope Domains tab ──────────────────────────────────────────────────────────
function ScopeDomainsTab() {
  const { data: domains = [], isLoading } = useQuery({
    queryKey: ["catalog", "scope-domains"],
    queryFn: () => api.get<any[]>("/api/v1/catalog/scope-domains"),
  });

  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) return <div className="py-12 text-center text-xs text-ink-500">Loading…</div>;

  return (
    <div className="space-y-2">
      <p className="text-xs text-ink-400 mb-4">
        Pre-built scope sets organised by industry. Expand a domain to browse individual scopes,
        then copy any scope string directly into a role or policy.
      </p>
      {domains.map((d: any) => {
        const open = expanded === d.domain;
        const riskCounts = (d.scopes as any[]).reduce((acc: Record<string, number>, s: any) => {
          acc[s.risk] = (acc[s.risk] || 0) + 1;
          return acc;
        }, {});

        return (
          <div key={d.domain}
            className="rounded-xl overflow-hidden"
            style={{ border: `1px solid ${open ? "var(--s0-accent-ring)" : "rgba(148,163,184,0.1)"}`, background: "rgba(148,163,184,0.02)" }}>

            {/* Header row */}
            <button
              type="button"
              onClick={() => setExpanded(open ? null : d.domain)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-ink-50">{d.label}</div>
                <div className="text-xs text-ink-400 mt-0.5">{d.description}</div>
              </div>

              {/* Risk summary pills */}
              <div className="hidden sm:flex items-center gap-1.5 shrink-0">
                {Object.entries(riskCounts).map(([risk, count]) => (
                  <span key={risk}
                    className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    style={{ background: RISK[risk]?.bg ?? "transparent", color: RISK[risk]?.text ?? "#94A3B8" }}>
                    {count} {risk}
                  </span>
                ))}
              </div>

              <div className="shrink-0 ml-2 text-ink-500">
                {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
              </div>
            </button>

            {/* Scope list */}
            {open && (
              <div style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
                <div className="divide-y divide-ink-800/60">
                  {(d.scopes as any[]).map((s: any) => (
                    <div key={s.scope}
                      className="flex items-center gap-3 px-4 py-2.5">
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-mono font-medium text-ink-100">{s.scope}</span>
                        <span className="text-[10px] text-ink-500 ml-2">{s.description}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                          style={{ background: RISK[s.risk]?.bg, color: RISK[s.risk]?.text }}>
                          {s.risk}
                        </span>
                        <CopyButton text={s.scope} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Policy Templates tab ───────────────────────────────────────────────────────
function PolicyTemplatesTab() {
  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["catalog", "policy-templates"],
    queryFn: () => api.get<any[]>("/api/v1/catalog/policy-templates"),
  });

  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) return <div className="py-12 text-center text-xs text-ink-500">Loading…</div>;

  return (
    <div className="space-y-2">
      <p className="text-xs text-ink-400 mb-4">
        Ready-made ABAC condition expressions. Copy the JSON into the condition editor on any policy,
        then adjust the values to match your requirements.
      </p>
      {templates.map((t: any) => {
        const open = expanded === t.id;
        const ef = EFFECT[t.suggested_effect] ?? EFFECT.allow;
        const conditionJson = JSON.stringify(t.condition, null, 2);

        return (
          <div key={t.id}
            className="rounded-xl overflow-hidden"
            style={{ border: `1px solid ${open ? "var(--s0-accent-ring)" : "rgba(148,163,184,0.1)"}`, background: "rgba(148,163,184,0.02)" }}>

            {/* Header row */}
            <button
              type="button"
              onClick={() => setExpanded(open ? null : t.id)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink-50">{t.label}</span>
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                    style={{ background: ef.bg, color: ef.text }}>
                    {t.suggested_effect}
                  </span>
                </div>
                <div className="text-xs text-ink-400 mt-0.5">{t.description}</div>
              </div>

              {/* Condition preview inline */}
              <code className="hidden md:block text-[10px] font-mono text-ink-600 truncate max-w-[220px] shrink-0">
                {JSON.stringify(t.condition).slice(0, 60)}{JSON.stringify(t.condition).length > 60 ? "…" : ""}
              </code>

              <div className="shrink-0 ml-2 text-ink-500">
                {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
              </div>
            </button>

            {/* Expanded condition */}
            {open && (
              <div style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
                <div className="px-4 py-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-ink-300">Condition JSON</span>
                    <CopyButton text={conditionJson} />
                  </div>
                  <pre
                    className="text-xs font-mono rounded-lg p-3 overflow-x-auto leading-relaxed"
                    style={{ background: "#0A1020", border: "1px solid rgba(148,163,184,0.08)", color: "#94A3B8" }}
                  >
                    {conditionJson}
                  </pre>

                  <div className="mt-3 rounded-lg px-3 py-2 text-[11px] text-ink-400"
                    style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-subtle)" }}>
                    <span className="font-semibold text-ink-200">How to use: </span>
                    Copy the JSON above, open a policy in the editor, paste it into the
                    <span className="font-mono text-ink-200"> Condition</span> field, and adjust the values
                    to fit your use case. Suggested effect: <span style={{ color: ef.text }}>{t.suggested_effect}</span>.
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Load-into-org modal ────────────────────────────────────────────────────────
interface ToolForm {
  namespace: string;
  name: string;
  description: string;
  risk_class: string;
  input_schema: string;
  scopes: string;
}

function LoadToolModal({
  tool,
  onClose,
}: {
  tool: any;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState<ToolForm>({
    namespace: tool.namespace,
    name: tool.name,
    description: tool.description,
    risk_class: tool.risk_class,
    input_schema: JSON.stringify(tool.input_schema ?? {}, null, 2),
    scopes: (tool.scopes as string[]).join("\n"),
  });
  const [schemaError, setSchemaError] = useState("");
  const [apiError, setApiError] = useState("");
  const [success, setSuccess] = useState(false);

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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tools"] });
      setSuccess(true);
    },
    onError: (err: unknown) => setApiError((err as any)?.message ?? "Failed to create tool"),
  });

  function setField(k: keyof ToolForm) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm(f => ({ ...f, [k]: e.target.value }));
      if (k === "input_schema") {
        try { JSON.parse(e.target.value); setSchemaError(""); }
        catch { setSchemaError("Invalid JSON"); }
      }
    };
  }

  if (success) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="bg-page-dark border border-ink-800 rounded-xl shadow-2xl w-full max-w-sm mx-4 p-8 text-center">
          <CheckCircle2 className="size-10 mx-auto mb-3" style={{ color: "#34D399" }} />
          <div className="text-base font-semibold text-ink-50 mb-1">Tool added to your org</div>
          <div className="text-xs text-ink-400 mb-5">
            <span className="font-mono text-ink-200">{form.namespace}.{form.name}</span> is now in your scope catalog.
            You can assign its scopes to roles from the{" "}
            <Link to="/app/tools" onClick={onClose} className="text-accent-400 underline">Scope Catalog</Link>.
          </div>
          <button className="btn-primary w-full" onClick={onClose}>Done</button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-page-dark border border-ink-800 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-800">
          <div>
            <h2 className="text-base font-semibold text-ink-50">{tool.display_name}</h2>
            <p className="text-xs text-ink-400 mt-0.5">Review and customise before adding to your org</p>
          </div>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-50 shrink-0 ml-4">
            <X className="size-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {/* Namespace + Name */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Namespace <span className="text-danger-400">*</span></label>
              <input className="input" value={form.namespace} onChange={setField("namespace")} placeholder="e.g. payments" />
            </div>
            <div>
              <label className="label">Name <span className="text-danger-400">*</span></label>
              <input className="input" value={form.name} onChange={setField("name")} placeholder="e.g. refund.issue" />
            </div>
          </div>

          <div>
            <label className="label">Description</label>
            <input className="input" value={form.description} onChange={setField("description")} placeholder="What does this tool do?" />
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
              rows={3}
              value={form.scopes}
              onChange={setField("scopes")}
              placeholder={"payments.refund.issue\npayments.read"}
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
              rows={8}
              value={form.input_schema}
              onChange={setField("input_schema")}
              spellCheck={false}
            />
          </div>

          {apiError && <p className="text-danger-400 text-xs">{apiError}</p>}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-ink-800">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            onClick={() => create.mutate()}
            disabled={!form.namespace || !form.name || !!schemaError || create.isPending}
          >
            {create.isPending ? "Adding…" : (
              <><Plus className="size-4" /> Add to org</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Tool Templates tab ─────────────────────────────────────────────────────────
function ToolTemplatesTab() {
  const { data: domains = [], isLoading } = useQuery({
    queryKey: ["catalog", "tool-templates"],
    queryFn: () => api.get<any[]>("/api/v1/catalog/tool-templates"),
  });

  const [expanded, setExpanded] = useState<string | null>(null);
  const [loadModal, setLoadModal] = useState<any | null>(null);

  if (isLoading) return <div className="py-12 text-center text-xs text-ink-500">Loading…</div>;

  return (
    <>
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-4 mb-4">
          <p className="text-xs text-ink-400">
            Pre-built tools organised by industry domain. Click a tool to open it in a pre-filled editor,
            customise the fields, then add it to your org's scope catalog in one click.
          </p>
          <Link
            to="/app/tools"
            className="flex items-center gap-1.5 text-[11px] font-medium shrink-0 transition-colors"
            style={{ color: "var(--s0-accent-text)" }}
          >
            <ExternalLink className="size-3" /> View your catalog
          </Link>
        </div>

        {domains.map((d: any) => {
          const open = expanded === d.domain;
          const riskCounts = (d.tools as any[]).reduce((acc: Record<string, number>, t: any) => {
            acc[t.risk_class] = (acc[t.risk_class] || 0) + 1;
            return acc;
          }, {});

          return (
            <div
              key={d.domain}
              className="rounded-xl overflow-hidden"
              style={{ border: `1px solid ${open ? "var(--s0-accent-ring)" : "rgba(148,163,184,0.1)"}`, background: "rgba(148,163,184,0.02)" }}
            >
              {/* Domain header */}
              <button
                type="button"
                onClick={() => setExpanded(open ? null : d.domain)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
              >
                <Wrench className="size-4 shrink-0" style={{ color: "var(--s0-accent-text)" }} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-ink-50">{d.label}</div>
                  <div className="text-xs text-ink-500 mt-0.5">{d.tools.length} pre-built tools</div>
                </div>

                {/* Risk summary pills */}
                <div className="hidden sm:flex items-center gap-1.5 shrink-0">
                  {Object.entries(riskCounts).map(([risk, count]) => (
                    <span
                      key={risk}
                      className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                      style={{ background: RISK[risk]?.bg ?? "transparent", color: RISK[risk]?.text ?? "#94A3B8" }}
                    >
                      {count as number} {risk}
                    </span>
                  ))}
                </div>

                <div className="shrink-0 ml-2 text-ink-500">
                  {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                </div>
              </button>

              {/* Tool list */}
              {open && (
                <div style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
                  <div className="divide-y divide-ink-800/40">
                    {(d.tools as any[]).map((t: any) => (
                      <div key={t.id} className="flex items-center gap-4 px-4 py-3 hover:bg-white/[0.015] transition-colors">
                        {/* Tool info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-ink-100">{t.display_name}</span>
                            <code className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(148,163,184,0.08)", color: "#94A3B8" }}>
                              {t.namespace}.{t.name}
                            </code>
                            <span
                              className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                              style={{ background: RISK[t.risk_class]?.bg, color: RISK[t.risk_class]?.text }}
                            >
                              {t.risk_class === "critical" && <AlertTriangle className="size-2.5 inline mr-0.5" />}
                              {t.risk_class}
                            </span>
                          </div>
                          <p className="text-xs text-ink-500 mt-0.5">{t.description}</p>
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {(t.scopes as string[]).map((s: string) => (
                              <span key={s} className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)", border: "1px solid var(--s0-accent-ring)" }}>
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Load button */}
                        <button
                          type="button"
                          onClick={() => setLoadModal(t)}
                          className="btn-ghost shrink-0 text-xs flex items-center gap-1.5"
                          style={{ color: "var(--s0-accent-text)" }}
                        >
                          <Plus className="size-3.5" /> Load into org
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Load tool modal */}
      {loadModal && (
        <LoadToolModal
          tool={loadModal}
          onClose={() => setLoadModal(null)}
        />
      )}
    </>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────
export default function CatalogPage() {
  const [tab, setTab] = useState<"tools" | "scopes" | "templates">("tools");

  return (
    <div>
      <PageHeader
        title="Library"
        subtitle="Pre-built tools, scope domains, and condition templates to bootstrap your permission setup."
      />

      <div className="px-8 py-6">
        {/* Tab bar */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl w-fit"
          style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.1)" }}>
          {[
            { key: "tools",     label: "Tool templates",    icon: Wrench },
            { key: "scopes",    label: "Scope domains",     icon: Layers },
            { key: "templates", label: "Policy templates",  icon: BookOpen },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key as any)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              style={tab === key
                ? { background: "var(--s0-accent-ring)", color: "var(--s0-accent-text)" }
                : { color: "#64748B" }}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </div>

        {tab === "tools"     && <ToolTemplatesTab />}
        {tab === "scopes"    && <ScopeDomainsTab />}
        {tab === "templates" && <PolicyTemplatesTab />}
      </div>
    </div>
  );
}
