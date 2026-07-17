import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2, ShieldCheck, Download, ExternalLink } from "lucide-react";

interface FrameworkRef { framework: string; ref: string; url?: string }
interface Control {
  id: string;
  name: string;
  frameworks: FrameworkRef[];
  status: "implemented" | "partial" | "not_configured";
  evidence: Record<string, unknown>;
  how_kynara_implements: string;
}
interface Evidence {
  organization_id: string;
  generated_at: string;
  summary: { controls_total: number; implemented: number; partial: number; not_configured: number };
  frameworks_covered: string[];
  controls: Control[];
}

const STATUS_META: Record<Control["status"], { label: string; color: string; bg: string }> = {
  implemented:    { label: "Implemented",    color: "#34D399", bg: "rgba(16,185,129,0.12)" },
  partial:        { label: "Partial",        color: "#FBBF24", bg: "rgba(245,158,11,0.12)" },
  not_configured: { label: "Not configured", color: "#F87171", bg: "rgba(244,63,94,0.12)" },
};

export default function CompliancePage() {
  const { data, isLoading } = useQuery<Evidence>({
    queryKey: ["compliance-evidence"],
    queryFn: () => api.get<Evidence>("/api/v1/compliance/evidence"),
    staleTime: 60_000,
  });

  const cardStyle = { background: "var(--s0-surface,#FAFAF9)", border: "1px solid rgba(148,163,184,.1)" };

  function exportJson() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kynara-compliance-evidence-${data.generated_at.slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-accent-500" />
          <h1 className="text-xl font-bold text-ink-50">Compliance Evidence</h1>
        </div>
        <div className="flex gap-2">
          <button onClick={exportJson}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg"
            style={{ background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)", border: "1px solid var(--s0-accent-ring)" }}>
            <Download className="w-3.5 h-3.5" /> Export JSON
          </button>
          <button onClick={() => window.print()}
            className="text-xs font-medium px-3 py-2 rounded-lg text-ink-300"
            style={{ background: "rgba(148,163,184,.06)", border: "1px solid rgba(148,163,184,.12)" }}>
            Print / PDF
          </button>
        </div>
      </div>
      <p className="text-sm text-ink-400 mb-6">
        Live mapping of this org's Kynara configuration to OWASP AI Exchange, MITRE ATLAS,
        ISO/IEC 42001 and EU AI Act controls. Statuses are computed from your actual
        policies, roles and audit chain at load time — evidence, not aspiration.
      </p>

      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-indigo-400" /></div>
      ) : data ? (
        <div className="space-y-4">
          {/* Summary */}
          <div className="rounded-xl p-5 flex items-center gap-8" style={cardStyle}>
            <div>
              <div className="text-3xl font-bold text-ink-50">
                {data.summary.implemented}<span className="text-ink-500 text-lg">/{data.summary.controls_total}</span>
              </div>
              <div className="text-xs text-ink-400 mt-0.5">controls implemented</div>
            </div>
            <div className="flex gap-5 text-sm">
              <span style={{ color: "#34D399" }}>{data.summary.implemented} implemented</span>
              <span style={{ color: "#FBBF24" }}>{data.summary.partial} partial</span>
              <span style={{ color: "#F87171" }}>{data.summary.not_configured} not configured</span>
            </div>
            <div className="ml-auto text-right">
              <div className="text-[10px] text-ink-500 uppercase tracking-wide">Generated</div>
              <div className="text-xs text-ink-300">{new Date(data.generated_at).toLocaleString()}</div>
            </div>
          </div>

          {/* Controls */}
          {data.controls.map((c) => {
            const meta = STATUS_META[c.status];
            return (
              <div key={c.id} className="rounded-xl p-5" style={cardStyle}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold text-ink-50">{c.name}</div>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {c.frameworks.map((f, i) => f.url ? (
                        <a key={i} href={f.url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded font-mono"
                          style={{ background: "rgba(148,163,184,.08)", color: "var(--s0-accent-text)" }}>
                          {f.framework}: {f.ref} <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span key={i} className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                          style={{ background: "rgba(148,163,184,.08)", color: "var(--s0-text-muted,#9CA3AF)" }}>
                          {f.framework}: {f.ref}
                        </span>
                      ))}
                    </div>
                  </div>
                  <span className="shrink-0 text-[10px] font-semibold px-2 py-1 rounded-full"
                    style={{ background: meta.bg, color: meta.color }}>
                    {meta.label}
                  </span>
                </div>
                <p className="text-xs text-ink-400 mt-3">{c.how_kynara_implements}</p>
                <div className="mt-2 rounded-lg p-3 font-mono text-[11px] text-ink-300 overflow-x-auto"
                  style={{ background: "rgba(148,163,184,.05)" }}>
                  {JSON.stringify(c.evidence)}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
