import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2, Download, Search, Tag } from "lucide-react";

interface Template {
  id: string; slug: string; display_name: string;
  description: string; category: string; author: string;
  tags: string[]; install_count: number;
}

interface TemplateDetail extends Template {
  policies: object[]; example_context: object;
}

const CATEGORY_COLORS: Record<string, string> = {
  "security":   "rgba(244,63,94,.12)",
  "compliance": "rgba(245,158,11,.12)",
  "finserv":    "rgba(16,185,129,.12)",
  "healthcare": "rgba(52,211,153,.12)",
  "devops":     "var(--s0-accent-subtle)",
  "default":    "rgba(148,163,184,.08)",
};
const CATEGORY_TEXT: Record<string, string> = {
  "security": "#F43F5E", "compliance": "#FCD34D",
  "finserv": "#34D399", "healthcare": "#2DD4BF",
  "devops": "var(--s0-accent-text)", "default": "#94A3B8",
};

export default function PolicyTemplatesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<TemplateDetail | null>(null);
  const [installing, setInstalling] = useState<string | null>(null);
  const [installed, setInstalled] = useState<Set<string>>(new Set());

  const { data: templates = [], isLoading } = useQuery<Template[]>({
    queryKey: ["policy-templates"],
    queryFn: () => api.get<Template[]>("/api/v1/templates"),
  });

  const installMutation = useMutation({
    mutationFn: (slug: string) => api.post(`/api/v1/templates/${slug}/install`),
    onSuccess: (_data, slug) => {
      setInstalled(prev => new Set([...prev, slug]));
      setInstalling(null);
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: () => setInstalling(null),
  });

  const filtered = templates.filter(t =>
    !search || t.display_name.toLowerCase().includes(search.toLowerCase()) ||
    t.category.toLowerCase().includes(search.toLowerCase()) ||
    t.tags.some(tag => tag.toLowerCase().includes(search.toLowerCase()))
  );

  const categories = [...new Set(templates.map(t => t.category))].sort();

  function handleInstall(slug: string) {
    setInstalling(slug);
    installMutation.mutate(slug);
  }

  const cardStyle = { background: "var(--s0-surface,#FAFAF9)", border: "1px solid rgba(148,163,184,.1)" };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-ink-50">Policy Templates</h1>
          <p className="text-sm text-ink-400 mt-0.5">Pre-built policies for common use cases — install with one click.</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search templates…"
            className="pl-8 pr-4 py-2 text-sm rounded-lg text-ink-100 placeholder:text-slate-600 outline-none w-52"
            style={{ background: "rgba(148,163,184,.06)", border: "1px solid rgba(148,163,184,.12)" }} />
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-indigo-400" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map(t => {
            const bg = CATEGORY_COLORS[t.category] || CATEGORY_COLORS.default;
            const tc = CATEGORY_TEXT[t.category] || CATEGORY_TEXT.default;
            const isInstalled = installed.has(t.slug);
            return (
              <div key={t.id} className="rounded-xl p-5 cursor-pointer transition-all hover:border-indigo-500/30"
                style={cardStyle} onClick={() => setSelected(t as TemplateDetail)}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-ink-50 text-sm mb-1">{t.display_name}</div>
                    <span className="inline-flex text-[10px] font-bold px-2 py-0.5 rounded"
                      style={{ background: bg, color: tc }}>
                      {t.category}
                    </span>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); handleInstall(t.slug); }}
                    disabled={isInstalled || installing === t.slug}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex-shrink-0"
                    style={isInstalled
                      ? { background: "rgba(16,185,129,.12)", color: "#34D399", border: "1px solid rgba(16,185,129,.3)" }
                      : { background: "var(--s0-accent-ring)", color: "var(--s0-accent-text)", border: "1px solid var(--s0-accent-ring)" }
                    }>
                    {installing === t.slug ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                    {isInstalled ? "Installed" : "Install"}
                  </button>
                </div>
                <p className="text-xs text-ink-400 leading-relaxed mb-3">{t.description}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  {t.tags.slice(0, 4).map(tag => (
                    <span key={tag} className="inline-flex items-center gap-1 text-[10px] text-ink-400 px-1.5 py-0.5 rounded"
                      style={{ background: "rgba(148,163,184,.06)" }}>
                      <Tag className="w-2.5 h-2.5" />{tag}
                    </span>
                  ))}
                  {t.install_count > 0 && (
                    <span className="ml-auto text-[10px] text-slate-600">{t.install_count} installs</span>
                  )}
                </div>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="col-span-2 text-center py-16 text-ink-400">
              No templates match "{search}"
            </div>
          )}
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)" }}
          onClick={() => setSelected(null)}>
          <div className="w-full max-w-2xl rounded-2xl p-7 overflow-y-auto max-h-[80vh]"
            style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,.12)" }}
            onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-lg font-bold text-ink-50">{selected.display_name}</h2>
              <button onClick={() => setSelected(null)} className="text-ink-400 hover:text-ink-50 text-xl leading-none">×</button>
            </div>
            <p className="text-sm text-ink-400 mb-4">{selected.description}</p>
            <div className="text-xs font-bold uppercase tracking-widest text-indigo-400 mb-2">Policies included</div>
            <pre className="text-xs text-ink-400 rounded-lg p-4 overflow-x-auto mb-5"
              style={{ background: "rgba(148,163,184,.05)", border: "1px solid rgba(148,163,184,.1)" }}>
              {JSON.stringify(selected.policies || [], null, 2)}
            </pre>
            <button onClick={() => { handleInstall(selected.slug); setSelected(null); }}
              disabled={installed.has(selected.slug)}
              className="w-full py-2.5 rounded-xl text-sm font-semibold text-ink-50"
              style={{ background: "linear-gradient(135deg,#18181B,#27272A)" }}>
              {installed.has(selected.slug) ? "Already installed" : "Install to my org"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
