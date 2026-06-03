import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bot, ShieldOff, ShieldCheck as ShieldOn, Clock, ShieldCheck, Plus, Trash2, Pencil,
  CheckCircle2, XCircle, AlertTriangle, ExternalLink, Copy, Check,
  Users, X,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ── helpers ────────────────────────────────────────────────────────────────
function EffectBadge({ effect }: { effect: string }) {
  if (effect === "allow")            return <span className="pill-ok"><CheckCircle2 className="size-3" />{effect}</span>;
  if (effect === "deny")             return <span className="pill-danger"><XCircle className="size-3" />{effect}</span>;
  return <span className="pill-warn"><AlertTriangle className="size-3" />{effect}</span>;
}


function CopyID({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <span className="flex items-center gap-1.5">
      <code className="font-mono text-[11px] text-ink-300">{value.slice(0, 8)}…{value.slice(-4)}</code>
      <button
        onClick={copy}
        title="Copy full ID"
        className="p-0.5 rounded hover:bg-white/10 transition-colors"
        style={{ color: copied ? "#10B981" : "#64748B" }}
      >
        {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
      </button>
    </span>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-xs border-t border-ink-800 pt-2 first:border-0 first:pt-0">
      <span className="text-ink-400">{k}</span>
      <span className="text-ink-200">{v}</span>
    </div>
  );
}

// ── main ────────────────────────────────────────────────────────────────────
export default function AgentDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [bindingOpen, setBindingOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState("");
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignUserId, setAssignUserId] = useState("");
  const [assignRoleId, setAssignRoleId] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editMode, setEditMode] = useState("");
  const [editModel, setEditModel] = useState("");
  const [editBudget, setEditBudget] = useState(10000);

  // ── data ──
  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.get<any[]>("/api/v1/agents"),
  });
  const agent = agents.find((a) => a.id === id);

  const { data: events = [] } = useQuery({
    queryKey: ["audit", "agent", id],
    queryFn: () => api.get<any[]>(`/api/v1/audit/events?actor=agent:${id}&limit=50`),
    enabled: !!id,
  });

  const { data: agentPolicies = [], refetch: refetchPolicies } = useQuery({
    queryKey: ["agent-policies", id],
    queryFn: () => api.get<any[]>(`/api/v1/agents/${id}/policies`),
    enabled: !!id,
  });

  const { data: allPolicies = [] } = useQuery({
    queryKey: ["policies"],
    queryFn: () => api.get<any[]>("/api/v1/policies"),
  });

  const { data: assignments = [], refetch: refetchAssignments } = useQuery({
    queryKey: ["agent-assignments", id],
    queryFn: () => api.get<any[]>(`/api/v1/agents/${id}/assignments`),
    enabled: !!id,
  });

  const { data: members = [] } = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<any[]>("/api/v1/org/members"),
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<any[]>("/api/v1/agents/roles"),
  });

  // ── mutations ──
  const kill = useMutation({
    mutationFn: () => api.post(`/api/v1/agents/${id}/kill`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });

  const reactivate = useMutation({
    mutationFn: () => api.post(`/api/v1/agents/${id}/reactivate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });

  const updateAgent = useMutation({
    mutationFn: () => api.patch(`/api/v1/agents/${id}`, {
      display_name: editName,
      description: editDesc,
      mode: editMode,
      model: editModel || null,
      daily_action_budget: editBudget,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      setEditOpen(false);
    },
  });

  function openEdit() {
    setEditName(agent.display_name);
    setEditDesc(agent.description || "");
    setEditMode(agent.mode);
    setEditModel(agent.model || "");
    setEditBudget(agent.daily_action_budget);
    setEditOpen(true);
  }

  const bind = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/policies/${selectedPolicy}/bindings`, {
        subject_selector: `agent:${id}`,
      }),
    onSuccess: () => {
      refetchPolicies();
      setBindingOpen(false);
      setSelectedPolicy("");
    },
  });

  const unbind = useMutation({
    mutationFn: ({ policyId, bindingId }: { policyId: string; bindingId: string }) =>
      api.del(`/api/v1/policies/${policyId}/bindings/${bindingId}`),
    onSuccess: () => refetchPolicies(),
  });

  const addAssignment = useMutation({
    mutationFn: () => api.post(`/api/v1/agents/${id}/assignments`, {
      user_id: assignUserId,
      role_id: assignRoleId || null,
    }),
    onSuccess: () => {
      refetchAssignments();
      setAssignOpen(false);
      setAssignUserId("");
      setAssignRoleId("");
    },
  });

  const removeAssignment = useMutation({
    mutationFn: (assignmentId: string) =>
      api.del(`/api/v1/agents/${id}/assignments/${assignmentId}`),
    onSuccess: () => refetchAssignments(),
  });

  // ── derived ──
  // Policies not yet bound to this agent (direct binding only)
  const boundPolicyIds = new Set(agentPolicies.map((p: any) => p.id));
  const unboundPolicies = allPolicies.filter((p: any) => !boundPolicyIds.has(p.id));

  if (!agent) {
    return <div className="p-8 text-ink-400 text-sm">Agent not found.</div>;
  }

  return (
    <div>
      <PageHeader
        title={agent.display_name}
        subtitle={agent.description || "No description."}
        actions={
          <div className="flex items-center gap-2">
            <button onClick={openEdit} className="btn-ghost">
              <Pencil className="size-4" /> Edit
            </button>
            {agent.is_active
              ? <button onClick={() => kill.mutate()} disabled={kill.isPending} className="btn-danger">
                  <ShieldOff className="size-4" /> Kill agent
                </button>
              : <button onClick={() => reactivate.mutate()} disabled={reactivate.isPending} className="btn-primary">
                  <ShieldOn className="size-4" /> Reactivate
                </button>
            }
          </div>
        }
      />

      <div className="px-8 py-6 grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* ── Runtime info ── */}
        <div className="card p-4 space-y-2">
          <div className="flex items-center gap-2 mb-3">
            <Bot className="size-4 text-accent-500" />
            <span className="font-medium text-sm">Runtime</span>
          </div>
          <Row k="Agent ID" v={<CopyID value={agent.id} />} />
          <Row k="Slug" v={<code className="font-mono">{agent.slug}</code>} />
          <Row k="Mode" v={<span className="pill-info">{agent.mode}</span>} />
          <Row k="Model" v={agent.model || "—"} />
          <Row k="Daily budget" v={agent.daily_action_budget.toLocaleString()} />
          <Row k="Created" v={new Date(agent.created_at).toLocaleDateString()} />
          <Row k="Last action" v={agent.last_action_at
            ? new Date(agent.last_action_at).toLocaleString() : "never"} />
          <Row k="Status" v={
            agent.is_active
              ? <span className="pill-ok">active</span>
              : <span className="pill-danger">disabled</span>
          } />
        </div>

        {/* ── Recent decisions ── */}
        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="size-4 text-ink-400" />
            <span className="font-medium text-sm">Recent decisions</span>
          </div>
          <table className="table">
            <thead><tr>
              <th>When</th><th>Scope</th><th>Resource</th><th>Effect</th><th>Reason</th>
            </tr></thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="text-ink-400 text-xs">{new Date(e.ts).toLocaleTimeString()}</td>
                  <td className="font-mono text-xs">{e.payload?.action || e.event_type}</td>
                  <td className="text-xs">{e.resource_type ? `${e.resource_type}:${e.resource_id || ""}` : "—"}</td>
                  <td><EffectBadge effect={e.outcome || "—"} /></td>
                  <td className="text-xs text-ink-400">{e.payload?.reason || "—"}</td>
                </tr>
              ))}
              {!events.length && (
                <tr><td colSpan={5} className="text-center text-ink-500 py-6 text-xs">No decisions yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Policy bindings ── */}
        <div className="card p-4 lg:col-span-3">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-accent-500" />
              <span className="font-medium text-sm">Applied policies</span>
              <span className="text-xs text-ink-500">
                — policies bound directly to this agent or via wildcard (<code className="font-mono text-[10px]">*</code>)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/app/policies/new" className="btn-ghost text-xs">
                <Plus className="size-3" /> New policy
              </Link>
              {unboundPolicies.length > 0 && (
                <button className="btn-primary text-xs" onClick={() => setBindingOpen(true)}>
                  <Plus className="size-3" /> Attach policy
                </button>
              )}
            </div>
          </div>

          {agentPolicies.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Pri</th><th>Policy</th><th>Scopes</th>
                  <th>Resources</th><th>Effect</th><th>Bound via</th><th>Enabled</th><th></th>
                </tr>
              </thead>
              <tbody>
                {agentPolicies.map((p: any) => {
                  // Find the direct binding for this agent (not wildcard) if present
                  const directBinding = p.bindings?.find(
                    (b: any) => b.subject_selector === `agent:${id}`
                  );
                  const wildcardBinding = p.bindings?.find(
                    (b: any) => b.subject_selector === "*"
                  );
                  const binding = directBinding || wildcardBinding;

                  return (
                    <tr key={p.id}>
                      <td className="font-mono text-xs text-ink-400">{p.priority}</td>
                      <td>
                        <Link to={`/app/policies/${p.id}`}
                          className="text-sm font-medium text-accent-500 hover:underline">
                          {p.display_name}
                        </Link>
                        <div className="text-xs text-ink-400">{p.description || "—"}</div>
                      </td>
                      <td className="text-xs font-mono">{(p.actions || []).join(", ") || "*"}</td>
                      <td className="text-xs font-mono">{(p.resource_types || []).join(", ") || "*"}</td>
                      <td><EffectBadge effect={p.effect} /></td>
                      <td>
                        <span className={directBinding ? "pill-info" : "pill text-ink-400"}>
                          {directBinding ? "direct" : "wildcard"}
                        </span>
                      </td>
                      <td>{p.is_enabled
                        ? <span className="pill-ok">on</span>
                        : <span className="pill-danger">off</span>}
                      </td>
                      <td>
                        {directBinding && (
                          <button
                            onClick={() => unbind.mutate({ policyId: p.id, bindingId: binding.id })}
                            className="text-ink-500 hover:text-danger-400 transition-colors p-1"
                            title="Remove binding"
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        )}
                        {wildcardBinding && !directBinding && (
                          <span className="text-xs text-ink-600" title="Wildcard binding — remove from policy editor">
                            <ExternalLink className="size-3" />
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-8">
              <ShieldCheck className="size-8 mx-auto mb-3 text-ink-700" />
              <p className="text-sm text-ink-400 mb-1">No policies bound to this agent yet.</p>
              <p className="text-xs text-ink-600 mb-4">
                Without a policy allowing actions, all requests from this agent will be denied by default.
              </p>
              <div className="flex items-center justify-center gap-3">
                <Link to="/app/policies/new" className="btn-ghost text-xs">
                  <Plus className="size-3" /> Create policy
                </Link>
                {unboundPolicies.length > 0 && (
                  <button className="btn-primary text-xs" onClick={() => setBindingOpen(true)}>
                    <Plus className="size-3" /> Attach existing policy
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Roles ── */}
        <div className="card p-4 lg:col-span-3">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="size-4 text-accent-500" />
              <span className="font-medium text-sm">Roles</span>
              <span className="text-xs text-ink-500">— users assigned to operate this agent with a specific role</span>
            </div>
            <button className="btn-primary text-xs" onClick={() => setAssignOpen(true)}>
              <Plus className="size-3" /> Add role
            </button>
          </div>

          {assignments.length > 0 ? (
            <table className="table">
              <thead>
                <tr><th>User</th><th>Role</th><th>Expires</th><th></th></tr>
              </thead>
              <tbody>
                {assignments.map((a: any) => (
                  <tr key={a.id}>
                    <td>
                      <div className="text-sm font-medium text-ink-100">{a.user_name || "—"}</div>
                      <div className="text-xs text-ink-500 font-mono">{a.user_email}</div>
                    </td>
                    <td>
                      {a.role_name
                        ? <span className="pill-info text-xs">{a.role_name}</span>
                        : <span className="text-xs text-ink-500">No role</span>}
                    </td>
                    <td className="text-xs text-ink-400">
                      {a.expires_at ? new Date(a.expires_at).toLocaleDateString() : "Never"}
                    </td>
                    <td>
                      <button
                        className="text-ink-500 hover:text-danger-400 transition-colors p-1"
                        title="Remove role"
                        onClick={() => removeAssignment.mutate(a.id)}
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
              <Users className="size-8 mx-auto mb-3 text-ink-700" />
              <p className="text-sm text-ink-400 mb-4">No roles assigned to this agent yet.</p>
              <button className="btn-primary text-xs" onClick={() => setAssignOpen(true)}>
                <Plus className="size-3" /> Add first role
              </button>
            </div>
          )}
        </div>

      </div>

      {/* ── Add role modal ── */}
      {assignOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-md rounded-2xl shadow-2xl"
            style={{ background: "#FFFFFF", border: "1px solid rgba(148,163,184,0.12)" }}>
            <div className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <div>
                <div className="text-base font-semibold text-ink-50">Add role</div>
                <div className="text-xs text-ink-400 mt-0.5">
                  Assign a user to operate <strong className="text-ink-200">{agent.display_name}</strong>.
                </div>
              </div>
              <button onClick={() => setAssignOpen(false)} className="text-ink-400 hover:text-ink-50">
                <X className="size-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="label">User <span className="text-danger-400">*</span></label>
                <select className="input" value={assignUserId} onChange={e => setAssignUserId(e.target.value)}>
                  <option value="">— select a user —</option>
                  {members.map((m: any) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.display_name || m.email} ({m.seat_role})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Role <span className="text-ink-500 font-normal">(optional)</span></label>
                <select className="input" value={assignRoleId} onChange={e => setAssignRoleId(e.target.value)}>
                  <option value="">— no role —</option>
                  {roles.map((r: any) => (
                    <option key={r.id} value={r.id}>{r.display_name} ({r.slug})</option>
                  ))}
                </select>
                <p className="text-[10px] text-ink-500 mt-1">
                  Roles grant specific scopes the policy engine will evaluate.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4"
              style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
              <button className="btn-ghost" onClick={() => setAssignOpen(false)}>Cancel</button>
              <button className="btn-primary" disabled={!assignUserId || addAssignment.isPending}
                onClick={() => addAssignment.mutate()}>
                {addAssignment.isPending ? "Saving…" : "Add assignment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit agent modal ── */}
      {editOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-md rounded-2xl shadow-2xl"
            style={{ background: "#FFFFFF", border: "1px solid rgba(148,163,184,0.12)" }}>
            <div className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <div>
                <div className="text-base font-semibold text-ink-50">Edit agent</div>
                <div className="text-xs text-ink-400 mt-0.5">Update identity and operating constraints.</div>
              </div>
              <button onClick={() => setEditOpen(false)} className="text-ink-400 hover:text-ink-50">
                <X className="size-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="label">Display name <span className="text-danger-400">*</span></label>
                <input className="input" value={editName} onChange={e => setEditName(e.target.value)} />
              </div>
              <div>
                <label className="label">Description</label>
                <textarea className="input" rows={2} value={editDesc}
                  onChange={e => setEditDesc(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Mode</label>
                  <select className="input" value={editMode} onChange={e => setEditMode(e.target.value)}>
                    <option value="human_supervised">human_supervised</option>
                    <option value="autonomous">autonomous</option>
                    <option value="restricted">restricted</option>
                  </select>
                </div>
                <div>
                  <label className="label">Model</label>
                  <input className="input" placeholder="e.g. claude-3-5-sonnet"
                    value={editModel} onChange={e => setEditModel(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="label">Daily action budget</label>
                <input className="input" type="number" min={1} value={editBudget}
                  onChange={e => setEditBudget(Number(e.target.value))} />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4"
              style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
              <button className="btn-ghost" onClick={() => setEditOpen(false)}>Cancel</button>
              <button className="btn-primary" disabled={!editName || updateAgent.isPending}
                onClick={() => updateAgent.mutate()}>
                {updateAgent.isPending ? "Saving…" : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Attach policy modal ── */}
      {bindingOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-md rounded-2xl shadow-2xl"
            style={{ background: "#FFFFFF", border: "1px solid rgba(148,163,184,0.12)" }}>
            <div className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <div>
                <div className="text-base font-semibold text-ink-50">Attach policy</div>
                <div className="text-xs text-ink-400 mt-0.5">
                  Bind an existing policy directly to <strong className="text-ink-200">{agent.display_name}</strong>.
                </div>
              </div>
            </div>
            <div className="px-6 py-5 space-y-3">
              <label className="label">Select policy</label>
              <select className="input" value={selectedPolicy}
                onChange={(e) => setSelectedPolicy(e.target.value)}>
                <option value="">— choose a policy —</option>
                {unboundPolicies.map((p: any) => (
                  <option key={p.id} value={p.id}>
                    [{p.effect}] {p.display_name} (priority {p.priority})
                  </option>
                ))}
              </select>
              {selectedPolicy && (
                <div className="rounded-lg px-4 py-3 text-xs text-ink-300"
                  style={{ background: "rgba(24,24,27,0.08)", border: "1px solid rgba(24,24,27,0.15)" }}>
                  This will create a binding with selector{" "}
                  <code className="font-mono text-accent-400">agent:{id}</code>.
                  The policy will be evaluated for all actions taken by this agent.
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4"
              style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
              <button className="btn-ghost" onClick={() => { setBindingOpen(false); setSelectedPolicy(""); }}>
                Cancel
              </button>
              <button className="btn-primary" disabled={!selectedPolicy || bind.isPending}
                onClick={() => bind.mutate()}>
                {bind.isPending ? "Attaching…" : "Attach policy"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
