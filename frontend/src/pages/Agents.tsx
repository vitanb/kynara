import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bot, Plus, Activity, ShieldOff, X } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

interface Agent {
  id: string; slug: string; display_name: string; description: string | null;
  mode: string; model: string | null; daily_action_budget: number;
  is_active: boolean; last_action_at: string | null; created_at: string;
}

const MODES = ["human_supervised", "autonomous", "read_only"] as const;

const defaultForm = {
  display_name: "",
  slug: "",
  description: "",
  mode: "human_supervised" as string,
  model: "claude-sonnet-4-6",
  daily_action_budget: 10000,
};

function slugify(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64);
}

export default function AgentsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(defaultForm);
  const [slugEdited, setSlugEdited] = useState(false);
  const [error, setError] = useState("");

  const { data = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<Agent[]>("/api/v1/agents"),
  });

  const create = useMutation({
    mutationFn: () => api.post<Agent>("/api/v1/agents", {
      slug: form.slug,
      display_name: form.display_name,
      description: form.description || null,
      mode: form.mode,
      model: form.model || null,
      daily_action_budget: form.daily_action_budget,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      setOpen(false);
      setForm(defaultForm);
      setSlugEdited(false);
      setError("");
    },
    onError: (err: unknown) => {
      setError((err as { message?: string })?.message ?? "Failed to create agent");
    },
  });

  function setField(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      const val = k === "daily_action_budget" ? Number(e.target.value) : e.target.value;
      if (k === "slug") setSlugEdited(true);
      setForm(f => ({
        ...f,
        [k]: val,
        // Auto-populate slug from display_name unless user has manually edited it
        ...(k === "display_name" && !slugEdited ? { slug: slugify(e.target.value) } : {}),
      }));
    };
  }

  function openModal() { setForm(defaultForm); setSlugEdited(false); setError(""); setOpen(true); }

  return (
    <div>
      <PageHeader
        title="Agents"
        subtitle="Every AI agent in your org — its current role, supervision mode, and recent activity."
        actions={<button className="btn-primary" onClick={openModal}><Plus className="size-4" /> New agent</button>}
      />

      <div className="px-8 py-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.map((a) => (
          <Link key={a.id} to={`/app/agents/${a.id}`}
            className="card p-4 hover:border-accent-600/50 transition">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <div className={`size-9 rounded-md flex items-center justify-center ${
                  a.is_active ? "bg-accent-600/20 text-accent-500" : "bg-ink-800 text-ink-500"
                }`}>
                  <Bot className="size-4" />
                </div>
                <div>
                  <div className="text-sm font-medium">{a.display_name}</div>
                  <div className="text-xs text-ink-400 font-mono">{a.slug}</div>
                </div>
              </div>
              {a.is_active
                ? <span className="pill-ok"><Activity className="size-3" /> active</span>
                : <span className="pill-danger"><ShieldOff className="size-3" /> disabled</span>}
            </div>
            <p className="mt-3 text-xs text-ink-400 line-clamp-2 min-h-[2rem]">{a.description || "—"}</p>
            <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-400">
              <span className="pill-info">{a.mode}</span>
              {a.model && <span className="pill">{a.model}</span>}
              <span className="ml-auto">budget {a.daily_action_budget.toLocaleString()}</span>
            </div>
          </Link>
        ))}
        {!data.length && (
          <div className="col-span-full card p-10 text-center">
            <Bot className="size-10 mx-auto mb-3 text-ink-600" />
            <div className="text-sm text-ink-300 font-medium mb-1">No agents yet</div>
            <p className="text-xs text-ink-500 mb-4">Register your first AI agent to start governing its tool access.</p>
            <button className="btn-primary mx-auto" onClick={openModal}>
              <Plus className="size-4" /> New agent
            </button>
          </div>
        )}
      </div>

      {/* ── New Agent Modal ── */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-lg rounded-2xl shadow-2xl"
            style={{ background: "var(--s0-card)", border: "1px solid rgba(148,163,184,0.12)" }}>
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <div>
                <div className="text-base font-semibold text-ink-50">Register new agent</div>
                <div className="text-xs text-ink-400 mt-0.5">Define the agent's identity and operating constraints.</div>
              </div>
              <button onClick={() => setOpen(false)}
                className="text-ink-400 hover:text-ink-50 transition-colors">
                <X className="size-5" />
              </button>
            </div>

            {/* Form */}
            <div className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="label">Display name</label>
                  <input className="input" placeholder="CRM Assistant"
                    value={form.display_name} onChange={setField("display_name")} />
                </div>
                <div className="col-span-2">
                  <label className="label">Slug <span className="text-ink-500 font-normal">(unique identifier)</span></label>
                  <input className="input font-mono" placeholder="crm-assistant"
                    value={form.slug} onChange={setField("slug")}
                    pattern="^[a-z0-9][a-z0-9\-_]*$" />
                </div>
                <div>
                  <label className="label">Mode</label>
                  <select className="input" value={form.mode} onChange={setField("mode")}>
                    {MODES.map(m => (
                      <option key={m} value={m}>{m.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Daily action budget</label>
                  <input className="input" type="number" min={0}
                    value={form.daily_action_budget} onChange={setField("daily_action_budget")} />
                </div>
                <div className="col-span-2">
                  <label className="label">Model <span className="text-ink-500 font-normal">(optional)</span></label>
                  <input className="input" placeholder="claude-sonnet-4-6"
                    value={form.model} onChange={setField("model")} />
                </div>
                <div className="col-span-2">
                  <label className="label">Description <span className="text-ink-500 font-normal">(optional)</span></label>
                  <textarea className="input resize-none" rows={2}
                    placeholder="What does this agent do?"
                    value={form.description} onChange={setField("description")} />
                </div>
              </div>

              {error && (
                <div className="rounded-lg px-4 py-3 text-sm text-red-300"
                  style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}>
                  {error}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4"
              style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
              <button className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
              <button className="btn-primary" onClick={() => create.mutate()}
                disabled={!form.display_name || !form.slug || create.isPending}>
                {create.isPending ? "Creating…" : "Create agent"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
