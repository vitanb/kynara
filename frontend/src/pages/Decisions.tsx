import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  CheckCircle2, XCircle, AlertTriangle, PlayCircle, Clock,
  ChevronDown, ChevronUp, Info,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

function EffectBadge({ effect }: { effect: string }) {
  if (effect === "allow")
    return <span className="pill-ok"><CheckCircle2 className="size-3" /> allow</span>;
  if (effect === "deny")
    return <span className="pill-danger"><XCircle className="size-3" /> deny</span>;
  return <span className="pill-warn"><AlertTriangle className="size-3" /> {effect}</span>;
}

const DEFAULT_CONTEXT = JSON.stringify({ ip_country: "US", time: "10:00" }, null, 2);

export default function DecisionsPage() {
  const [subjectType, setSubjectType] = useState("agent");
  const [subjectId, setSubjectId]     = useState("");
  const [onBehalfOf, setOnBehalfOf]   = useState("");
  const [action, setAction]           = useState("");
  const [resourceType, setResourceType] = useState("");
  const [resourceId, setResourceId]   = useState("");
  const [context, setContext]         = useState(DEFAULT_CONTEXT);
  const [contextError, setContextError] = useState("");
  const [result, setResult]           = useState<any>(null);
  const [showCtx, setShowCtx]         = useState(false);
  const [history, setHistory]         = useState<any[]>([]);

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<any[]>("/api/v1/agents"),
  });

  const { data: members = [] } = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<any[]>("/api/v1/org/members"),
  });

  const { data: apiKeys = [] } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<any[]>("/api/v1/api-keys"),
  });

  const simulate = useMutation({
    mutationFn: async () => {
      let ctx: Record<string, unknown> = {};
      try { ctx = JSON.parse(context); } catch { throw new Error("Context is not valid JSON"); }
      return api.post<any>("/api/v1/decisions/check", {
        subject_type: subjectType,
        subject_id: subjectId,
        on_behalf_of_user_id: onBehalfOf || null,
        action,
        resource: { type: resourceType || null, id: resourceId || null, attrs: {} },
        context: ctx,
      });
    },
    onSuccess: (d) => {
      setResult(d);
      setHistory(h => [{
        ts: new Date().toLocaleTimeString(),
        subjectType, subjectId, onBehalfOf, action,
        resourceType, resourceId,
        effect: d.effect,
        reason: d.reason,
        policyId: d.matched_policy_id,
      }, ...h].slice(0, 20));
    },
    onError: (err: any) => {
      setResult({ error: err.message || "Request failed" });
    },
  });

  const effectColors: Record<string, any> = {
    allow:            { text: "#34D399", bg: "rgba(16,185,129,0.08)",  border: "rgba(16,185,129,0.2)" },
    deny:             { text: "#F87171", bg: "rgba(244,63,94,0.08)",   border: "rgba(190,18,60,0.2)" },
    require_approval: { text: "#FBBF24", bg: "rgba(245,158,11,0.08)", border: "rgba(180,83,9,0.25)" },
  };
  const ec = result && !result.error ? (effectColors[result.effect] || effectColors.deny) : null;

  return (
    <div>
      <PageHeader
        title="Policy Simulator"
        subtitle="Test any permission request against the live policy engine. See exactly which gate blocked it and why."
      />

      <div className="px-8 py-6 grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Simulator ── */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <PlayCircle className="size-4 text-accent-500" />
            <span className="font-medium text-sm">Policy simulator</span>
          </div>

          {/* Subject */}
          <div>
            <label className="label">Subject</label>
            <div className="flex gap-2">
              <select
                className="input w-36 shrink-0"
                value={subjectType}
                onChange={e => { setSubjectType(e.target.value); setSubjectId(""); setOnBehalfOf(""); }}
              >
                <option value="agent">agent</option>
                <option value="user">user</option>
                <option value="api_key">api_key</option>
              </select>
              {subjectType === "agent" ? (
                <select
                  className="input flex-1"
                  value={subjectId}
                  onChange={e => setSubjectId(e.target.value)}
                >
                  <option value="">— select agent —</option>
                  {(agents as any[]).map((a: any) => (
                    <option key={a.id} value={a.id}>{a.display_name} ({a.slug})</option>
                  ))}
                </select>
              ) : subjectType === "user" ? (
                <select
                  className="input flex-1"
                  value={subjectId}
                  onChange={e => setSubjectId(e.target.value)}
                >
                  <option value="">— select user —</option>
                  {(members as any[]).map((m: any) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.display_name || m.email} ({m.seat_role})
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  className="input flex-1"
                  value={subjectId}
                  onChange={e => setSubjectId(e.target.value)}
                >
                  <option value="">— select API key —</option>
                  {(apiKeys as any[]).map((k: any) => (
                    <option key={k.id} value={k.id}>
                      {k.name} ({k.prefix}…{k.last_four})
                    </option>
                  ))}
                </select>
              )}
            </div>
            <p className="text-[10px] text-ink-500 mt-1">
              The agent or user requesting the scope check.
            </p>
          </div>

          {/* On behalf of (agent mode) */}
          {subjectType === "agent" && (
            <div>
              <label className="label">
                On behalf of user
                <span className="text-ink-500 font-normal ml-1">(optional — for delegated agents)</span>
              </label>
              <select
                className="input"
                value={onBehalfOf}
                onChange={e => setOnBehalfOf(e.target.value)}
              >
                <option value="">— autonomous (uses agent role assignments) —</option>
                {(members as any[]).map((m: any) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.display_name || m.email} ({m.seat_role})
                  </option>
                ))}
              </select>
              <div className="flex items-start gap-1.5 mt-1.5 text-[10px] text-ink-500">
                <Info className="size-3 shrink-0 mt-0.5" />
                <span>
                  <strong className="text-ink-400">Autonomous</strong> — scopes come from the agent's role assignments.{" "}
                  <strong className="text-ink-400">Delegated</strong> — scopes are the <em>intersection</em> of the agent's role and the user's role (non-escalation guarantee).
                </span>
              </div>
            </div>
          )}

          {/* Scope */}
          <div>
            <label className="label">Scope</label>
            <input
              className="input font-mono"
              placeholder="e.g. infra:restart"
              value={action}
              onChange={e => setAction(e.target.value)}
            />
            <p className="text-[10px] text-ink-500 mt-1">
              The scope being requested (must match a scope granted by the agent's role).
            </p>
          </div>

          {/* Resource */}
          <div>
            <label className="label">Resource <span className="text-ink-500 font-normal">(optional)</span></label>
            <div className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="type  e.g. payment"
                value={resourceType}
                onChange={e => setResourceType(e.target.value)}
              />
              <input
                className="input flex-1"
                placeholder="id  e.g. pay_123"
                value={resourceId}
                onChange={e => setResourceId(e.target.value)}
              />
            </div>
          </div>

          {/* Context */}
          <div>
            <button
              className="flex items-center gap-1.5 text-xs text-ink-400 hover:text-ink-200 transition-colors mb-2"
              onClick={() => setShowCtx(s => !s)}
            >
              {showCtx ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
              Context JSON {contextError && <span className="text-danger-400 ml-1">(invalid JSON)</span>}
            </button>
            {showCtx && (
              <textarea
                className={`input font-mono text-xs ${contextError ? "border-danger-500" : ""}`}
                rows={5}
                value={context}
                spellCheck={false}
                onChange={e => {
                  setContext(e.target.value);
                  try { JSON.parse(e.target.value); setContextError(""); }
                  catch { setContextError("invalid"); }
                }}
              />
            )}
            <p className="text-[10px] text-ink-500 mt-1">
              Runtime context: ip_country, time, user attributes, etc.
            </p>
          </div>

          <button
            className="btn-primary w-full"
            disabled={!subjectId || !action || !!contextError || simulate.isPending}
            onClick={() => simulate.mutate()}
          >
            <PlayCircle className="size-4" />
            {simulate.isPending ? "Evaluating…" : "Evaluate"}
          </button>
        </div>

        {/* ── Result + History ── */}
        <div className="space-y-4">

          {/* Result */}
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="size-4 text-ink-500" />
              <span className="font-medium text-sm">Result</span>
            </div>

            {!result && (
              <div className="text-center py-10 text-ink-500 text-sm">
                Run the simulator to see the policy decision.
              </div>
            )}

            {result?.error && (
              <div className="rounded-lg px-4 py-3 text-sm text-danger-400"
                style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(190,18,60,0.2)" }}>
                {result.error}
              </div>
            )}

            {result && !result.error && ec && (
              <div className="space-y-3">
                <div className="rounded-lg px-4 py-4 flex items-center gap-3"
                  style={{ background: ec.bg, border: `1px solid ${ec.border}` }}>
                  {result.effect === "allow"
                    ? <CheckCircle2 className="size-6 shrink-0" style={{ color: ec.text }} />
                    : result.effect === "deny"
                    ? <XCircle className="size-6 shrink-0" style={{ color: ec.text }} />
                    : <AlertTriangle className="size-6 shrink-0" style={{ color: ec.text }} />}
                  <div>
                    <div className="font-semibold text-sm" style={{ color: ec.text }}>
                      {result.effect.toUpperCase().replace("_", " ")}
                    </div>
                    <div className="text-xs text-ink-400 mt-0.5">{result.reason}</div>
                  </div>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex justify-between border-t border-ink-800 pt-2">
                    <span className="text-ink-400">Effect</span>
                    <EffectBadge effect={result.effect} />
                  </div>
                  <div className="flex justify-between border-t border-ink-800 pt-2">
                    <span className="text-ink-400">Reason</span>
                    <span className="text-ink-200 max-w-[60%] text-right">{result.reason}</span>
                  </div>
                  {/* RBAC gate indicator */}
                  <div className="flex justify-between border-t border-ink-800 pt-2">
                    <span className="text-ink-400">Gate 1 · RBAC</span>
                    {result.rbac_pass === false
                      ? <span className="pill-danger text-[10px]">blocked — no matching scope</span>
                      : <span className="pill-ok text-[10px]">passed</span>
                    }
                  </div>
                  {/* Granted scopes */}
                  <div className="border-t border-ink-800 pt-2">
                    <span className="text-ink-400 block mb-1">Gate 1 · Granted scopes</span>
                    {result.granted_scopes?.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {result.granted_scopes.map((s: string) => (
                          <span key={s} className="font-mono text-[10px] bg-ink-800 text-ink-300 rounded px-1.5 py-0.5">{s}</span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-danger-400 text-[10px]">none — assign a Role to this agent</span>
                    )}
                  </div>
                  <div className="flex justify-between border-t border-ink-800 pt-2">
                    <span className="text-ink-400">Gate 2 · Matched policy</span>
                    <span className="font-mono text-ink-300">
                      {result.matched_policy_id
                        ? result.matched_policy_id.slice(0, 12) + "…"
                        : result.rbac_pass === false ? "skipped" : "none (default deny)"}
                    </span>
                  </div>
                  {result.approval_id && (
                    <div className="flex justify-between border-t border-ink-800 pt-2">
                      <span className="text-ink-400">Approval ID</span>
                      <span className="font-mono text-warn-400">{result.approval_id.slice(0, 12)}…</span>
                    </div>
                  )}
                  {result.obligations?.length > 0 && (
                    <div className="border-t border-ink-800 pt-2">
                      <span className="text-ink-400 block mb-1">Obligations</span>
                      <pre className="text-ink-300 text-[10px] bg-ink-900 rounded p-2 overflow-x-auto">
                        {JSON.stringify(result.obligations, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* History */}
          {history.length > 0 && (
            <div className="card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="size-4 text-ink-500" />
                <span className="font-medium text-sm">Session history</span>
                <span className="text-xs text-ink-500">({history.length})</span>
              </div>
              <table className="table">
                <thead>
                  <tr><th>Time</th><th>Subject</th><th>Scope</th><th>Effect</th></tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={i} className="cursor-pointer hover:bg-white/5"
                      onClick={() => {
                        setSubjectType(h.subjectType);
                        setSubjectId(h.subjectId);
                        setOnBehalfOf(h.onBehalfOf || "");
                        setAction(h.action);
                        setResourceType(h.resourceType);
                        setResourceId(h.resourceId);
                      }}
                    >
                      <td className="text-xs text-ink-400 font-mono">{h.ts}</td>
                      <td className="text-xs">
                        <span className="text-ink-500">{h.subjectType}:</span>
                        <span className="font-mono">{h.subjectId}</span>
                      </td>
                      <td className="text-xs font-mono">{h.action}</td>
                      <td><EffectBadge effect={h.effect} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-[10px] text-ink-600 mt-2">Click a row to reload those inputs.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
