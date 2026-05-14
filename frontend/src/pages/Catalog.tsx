import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, ChevronRight, Copy, Layers, BookOpen } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── Risk colours ──────────────────────────────────────────────────────────────
const RISK: Record<string, { bg: string; text: string }> = {
  low:      { bg: "rgba(16,185,129,0.12)",  text: "#34D399" },
  medium:   { bg: "rgba(245,158,11,0.12)",  text: "#FBBF24" },
  high:     { bg: "rgba(244,63,94,0.12)",   text: "#F87171" },
  critical: { bg: "rgba(168,85,247,0.12)",  text: "#C084FC" },
};

const EFFECT: Record<string, { bg: string; text: string }> = {
  allow:            { bg: "rgba(16,185,129,0.12)",  text: "#34D399" },
  deny:             { bg: "rgba(244,63,94,0.12)",   text: "#F87171" },
  require_approval: { bg: "rgba(245,158,11,0.12)",  text: "#FBBF24" },
};

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
      style={{ background: "rgba(99,102,241,0.1)", color: copied ? "#34D399" : "#818CF8", border: "1px solid rgba(99,102,241,0.2)" }}
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
            style={{ border: `1px solid ${open ? "rgba(99,102,241,0.3)" : "rgba(148,163,184,0.1)"}`, background: "rgba(148,163,184,0.02)" }}>

            {/* Header row */}
            <button
              type="button"
              onClick={() => setExpanded(open ? null : d.domain)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-white">{d.label}</div>
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
            style={{ border: `1px solid ${open ? "rgba(99,102,241,0.3)" : "rgba(148,163,184,0.1)"}`, background: "rgba(148,163,184,0.02)" }}>

            {/* Header row */}
            <button
              type="button"
              onClick={() => setExpanded(open ? null : t.id)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{t.label}</span>
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
                    style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.12)" }}>
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

// ── Main ───────────────────────────────────────────────────────────────────────
export default function CatalogPage() {
  const [tab, setTab] = useState<"scopes" | "templates">("scopes");

  return (
    <div>
      <PageHeader
        title="Catalog"
        subtitle="Pre-built scope domains by industry and condition templates to bootstrap policies."
      />

      <div className="px-8 py-6">
        {/* Tab bar */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl w-fit"
          style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.1)" }}>
          {[
            { key: "scopes",    label: "Scope domains",     icon: Layers },
            { key: "templates", label: "Policy templates",  icon: BookOpen },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key as any)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              style={tab === key
                ? { background: "rgba(99,102,241,0.2)", color: "#818CF8" }
                : { color: "#64748B" }}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </div>

        {tab === "scopes"    && <ScopeDomainsTab />}
        {tab === "templates" && <PolicyTemplatesTab />}
      </div>
    </div>
  );
}
