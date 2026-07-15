import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useNavigate } from "react-router-dom";
import {
  Shield, Building2, Users, ChevronDown, ChevronRight,
  Edit2, Trash2, Check, X, RefreshCw, UserCheck, UserX,
  Crown, AlertTriangle, Plus, Mail, Copy, Link2, LifeBuoy,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface AdminMember {
  user_id: string; email: string; display_name: string | null;
  seat_role: string; is_active: boolean; is_superadmin: boolean;
  mfa_enrolled: boolean; last_login_at: string | null;
}

interface AdminSubscription {
  plan: string; status: string; seats_included: number;
  decisions_included: number; current_period_end: string | null;
}

interface AdminOrg {
  org_id: string; name: string; slug: string; plan: string;
  created_at: string | null; member_count: number;
  members: AdminMember[]; subscription: AdminSubscription | null;
}

interface AdminUser {
  user_id: string; email: string; display_name: string | null;
  is_active: boolean; is_superadmin: boolean; mfa_enrolled: boolean;
  last_login_at: string | null; orgs: { org_id: string; org_name: string; seat_role: string }[];
  created_at: string | null;
}

interface AdminAgent {
  id: string; slug: string; display_name: string; description: string | null;
  mode: string; model: string | null; is_active: boolean;
  daily_action_budget: number; last_action_at: string | null; created_at: string | null;
}

interface AdminApproval {
  id: string; subject_type: string; subject_id: string; action: string;
  resource_type: string | null; resource_id: string | null; status: string;
  matched_policy_id: string | null; reviewed_by_user_id: string | null;
  reviewed_at: string | null; expires_at: string; created_at: string;
}

const APPROVAL_COLORS: Record<string, string> = {
  pending: "#ca8a04", approved: "#16a34a", rejected: "#ef4444", expired: "var(--s0-muted-text)",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, string> = {
  free: "var(--s0-muted-text)",
  starter: "var(--s0-accent-text)",
  pro: "#7c3aed",
  enterprise: "#b45309",
};

const ROLE_COLORS: Record<string, string> = {
  owner: "#b45309", admin: "#7c3aed", developer: "var(--s0-accent-text)",
  auditor: "#0891b2", member: "var(--s0-muted-text)",
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 99,
      border: `1px solid ${color}`, color, textTransform: "uppercase", letterSpacing: "0.05em",
    }}>{label}</span>
  );
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

// ── Inline edit helpers ───────────────────────────────────────────────────────

function EditableText({
  value, onSave,
}: { value: string; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value);
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!val.trim() || val === value) { setEditing(false); return; }
    setSaving(true);
    try { await onSave(val.trim()); setEditing(false); } finally { setSaving(false); }
  }

  if (!editing) return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      {value}
      <button onClick={() => setEditing(true)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-muted-text)", padding: 0 }}>
        <Edit2 size={13} />
      </button>
    </span>
  );
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <input value={val} onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
        autoFocus style={{
          background: "var(--s0-surface)", border: "1px solid var(--s0-border)",
          borderRadius: 4, color: "var(--s0-text)", padding: "2px 6px", fontSize: 13,
        }} />
      <button onClick={save} disabled={saving} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-accent-text)" }}><Check size={13} /></button>
      <button onClick={() => { setEditing(false); setVal(value); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-danger, #ef4444)" }}><X size={13} /></button>
    </span>
  );
}

// ── Org row ───────────────────────────────────────────────────────────────────

function OrgRow({ org, onRefresh }: { org: AdminOrg; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [planEdit, setPlanEdit] = useState(false);
  const [newPlan, setNewPlan] = useState(org.plan);
  const [saving, setSaving] = useState(false);
  const [roleEdits, setRoleEdits] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);

  // Invite state
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("developer");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteErr, setInviteErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Support view — agents & approvals (read-only, cross-tenant, audited)
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportLoaded, setSupportLoaded] = useState(false);
  const [supportLoading, setSupportLoading] = useState(false);
  const [supportErr, setSupportErr] = useState<string | null>(null);
  const [agents, setAgents] = useState<AdminAgent[]>([]);
  const [approvals, setApprovals] = useState<AdminApproval[]>([]);

  async function loadSupport() {
    setSupportLoading(true); setSupportErr(null);
    try {
      const [a, ap] = await Promise.all([
        api.get<AdminAgent[]>(`/api/v1/admin/orgs/${org.org_id}/agents`),
        api.get<AdminApproval[]>(`/api/v1/admin/orgs/${org.org_id}/approvals?limit=50`),
      ]);
      setAgents(a); setApprovals(ap); setSupportLoaded(true);
    } catch (e: any) { setSupportErr(e.message || "Failed to load support data"); }
    finally { setSupportLoading(false); }
  }

  function toggleSupport() {
    const next = !supportOpen;
    setSupportOpen(next);
    if (next && !supportLoaded) loadSupport();
  }

  async function createInvite() {
    setInviteBusy(true);
    setInviteErr(null);
    try {
      const r = await api.post<any>(`/api/v1/admin/orgs/${org.org_id}/invites`, {
        email: inviteEmail.trim() || null,
        seat_role: inviteRole,
      });
      const link = `${window.location.origin}/invite?token=${r.token}`;
      setInviteLink(link);
      setInviteEmail("");
    } catch (e: any) {
      setInviteErr(e.message || "Failed to create invite");
    } finally {
      setInviteBusy(false);
    }
  }

  function copyInviteLink() {
    if (!inviteLink) return;
    navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function savePlan() {
    if (newPlan === org.plan) { setPlanEdit(false); return; }
    setSaving(true);
    try {
      await api.patch(`/api/v1/admin/orgs/${org.org_id}`, { plan: newPlan });
      onRefresh();
      setPlanEdit(false);
    } catch (e: any) {
      setErr(e.message || "Failed to update plan");
    } finally { setSaving(false); }
  }

  async function saveName(name: string) {
    await api.patch(`/api/v1/admin/orgs/${org.org_id}`, { name });
    onRefresh();
  }

  async function deleteOrg() {
    setDeleting(true);
    try {
      await api.del(`/api/v1/admin/orgs/${org.org_id}`);
      onRefresh();
    } catch (e: any) {
      setErr(e.message || "Failed to delete org");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function saveMemberRole(userId: string) {
    const role = roleEdits[userId];
    if (!role) return;
    try {
      await api.patch(`/api/v1/admin/orgs/${org.org_id}/members/${userId}`, { seat_role: role });
      setRoleEdits(r => { const n = { ...r }; delete n[userId]; return n; });
      onRefresh();
    } catch (e: any) { setErr(e.message || "Failed to update role"); }
  }

  async function removeMember(userId: string) {
    try {
      await api.del(`/api/v1/admin/orgs/${org.org_id}/members/${userId}`);
      onRefresh();
    } catch (e: any) { setErr(e.message || "Failed to remove member"); }
  }

  const card: React.CSSProperties = {
    background: "var(--s0-surface)", border: "1px solid var(--s0-border)",
    borderRadius: 10, marginBottom: 10, overflow: "hidden",
  };
  const header: React.CSSProperties = {
    display: "flex", alignItems: "center", gap: 12, padding: "14px 18px",
    cursor: "pointer", userSelect: "none",
  };

  return (
    <div style={card}>
      <div style={header} onClick={() => setExpanded(e => !e)}>
        <span style={{ color: "var(--s0-muted-text)" }}>
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
        <Building2 size={16} style={{ color: "var(--s0-accent-text)", flexShrink: 0 }} />
        <span style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>
          <EditableText value={org.name} onSave={saveName} />
        </span>
        <span style={{ fontSize: 12, color: "var(--s0-muted-text)" }}>{org.slug}</span>
        <Badge label={org.plan} color={PLAN_COLORS[org.plan] || "var(--s0-muted-text)"} />
        {org.subscription && (
          <Badge
            label={org.subscription.status}
            color={org.subscription.status === "active" ? "#16a34a" : org.subscription.status === "trialing" ? "#ca8a04" : "#ef4444"}
          />
        )}
        <span style={{ fontSize: 12, color: "var(--s0-muted-text)" }}>{org.member_count} member{org.member_count !== 1 ? "s" : ""}</span>
        <span style={{ fontSize: 12, color: "var(--s0-muted-text)" }}>Created {fmtDate(org.created_at)}</span>
      </div>

      {expanded && (
        <div style={{ borderTop: "1px solid var(--s0-border)", padding: "16px 18px" }}>
          {err && (
            <div style={{ color: "#ef4444", fontSize: 13, marginBottom: 10 }}>{err}
              <button onClick={() => setErr(null)} style={{ marginLeft: 8, background: "none", border: "none", cursor: "pointer", color: "inherit" }}><X size={12} /></button>
            </div>
          )}

          {/* Subscription panel */}
          {org.subscription && (
            <div style={{ marginBottom: 16, padding: "10px 14px", background: "var(--s0-bg)", borderRadius: 8, fontSize: 13 }}>
              <strong style={{ fontSize: 12, color: "var(--s0-muted-text)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Subscription</strong>
              <div style={{ marginTop: 6, display: "flex", gap: 24, flexWrap: "wrap" }}>
                <span>Seats: <strong>{org.subscription.seats_included}</strong></span>
                <span>Decisions/mo: <strong>{org.subscription.decisions_included.toLocaleString()}</strong></span>
                {org.subscription.current_period_end && (
                  <span>Period ends: <strong>{fmtDate(org.subscription.current_period_end)}</strong></span>
                )}
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  Plan:&nbsp;
                  {planEdit ? (
                    <>
                      <select value={newPlan} onChange={e => setNewPlan(e.target.value)}
                        style={{ background: "var(--s0-surface)", border: "1px solid var(--s0-border)", borderRadius: 4, color: "var(--s0-text)", padding: "2px 6px", fontSize: 12 }}>
                        {["free","starter","pro","enterprise"].map(p => <option key={p} value={p}>{p}</option>)}
                      </select>
                      <button onClick={savePlan} disabled={saving} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-accent-text)" }}><Check size={13} /></button>
                      <button onClick={() => { setPlanEdit(false); setNewPlan(org.plan); }} style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444" }}><X size={13} /></button>
                    </>
                  ) : (
                    <>
                      <strong>{org.plan}</strong>
                      <button onClick={() => setPlanEdit(true)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-muted-text)" }}><Edit2 size={12} /></button>
                    </>
                  )}
                </span>
              </div>
            </div>
          )}

          {/* Members table */}
          <strong style={{ fontSize: 12, color: "var(--s0-muted-text)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Members</strong>
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8, fontSize: 13 }}>
            <thead>
              <tr style={{ color: "var(--s0-muted-text)", textAlign: "left" }}>
                {["User","Role","Status","Last Login","Actions"].map(h => (
                  <th key={h} style={{ padding: "4px 8px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {org.members.map(m => (
                <tr key={m.user_id} style={{ borderTop: "1px solid var(--s0-border)" }}>
                  <td style={{ padding: "8px 8px" }}>
                    <div style={{ fontWeight: 500 }}>{m.display_name || m.email}</div>
                    <div style={{ fontSize: 11, color: "var(--s0-muted-text)" }}>{m.email}</div>
                  </td>
                  <td style={{ padding: "8px 8px" }}>
                    {roleEdits[m.user_id] !== undefined ? (
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <select value={roleEdits[m.user_id]} onChange={e => setRoleEdits(r => ({ ...r, [m.user_id]: e.target.value }))}
                          style={{ background: "var(--s0-surface)", border: "1px solid var(--s0-border)", borderRadius: 4, color: "var(--s0-text)", padding: "2px 4px", fontSize: 12 }}>
                          {["owner","admin","developer","auditor","member"].map(r => <option key={r} value={r}>{r}</option>)}
                        </select>
                        <button onClick={() => saveMemberRole(m.user_id)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-accent-text)" }}><Check size={12} /></button>
                        <button onClick={() => setRoleEdits(r => { const n={...r}; delete n[m.user_id]; return n; })} style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444" }}><X size={12} /></button>
                      </span>
                    ) : (
                      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Badge label={m.seat_role} color={ROLE_COLORS[m.seat_role] || "var(--s0-muted-text)"} />
                        <button onClick={() => setRoleEdits(r => ({ ...r, [m.user_id]: m.seat_role }))} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--s0-muted-text)" }}><Edit2 size={12} /></button>
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "8px 8px" }}>
                    <Badge label={m.is_active ? "active" : "inactive"} color={m.is_active ? "#16a34a" : "#ef4444"} />
                  </td>
                  <td style={{ padding: "8px 8px", color: "var(--s0-muted-text)", fontSize: 12 }}>{fmtDate(m.last_login_at)}</td>
                  <td style={{ padding: "8px 8px" }}>
                    <button onClick={() => removeMember(m.user_id)} title="Remove from org"
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444" }}><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Invite member */}
          <div style={{ marginTop: 16 }}>
            {!showInvite && !inviteLink && (
              <button
                onClick={() => { setShowInvite(true); setInviteErr(null); }}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "6px 14px", borderRadius: 7, fontSize: 12, fontWeight: 500,
                  background: "var(--s0-accent-subtle)", color: "var(--s0-accent-text)",
                  border: "1px solid var(--s0-accent-ring)", cursor: "pointer",
                }}
              >
                <Mail size={13} /> Invite Member
              </button>
            )}

            {showInvite && !inviteLink && (
              <div style={{ background: "var(--s0-bg)", border: "1px solid var(--s0-border)", borderRadius: 8, padding: "14px 16px" }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--s0-text)", marginBottom: 10 }}>
                  Invite a member to <em>{org.name}</em>
                </div>
                {inviteErr && (
                  <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 8 }}>{inviteErr}</div>
                )}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
                  <div style={{ flex: "1 1 180px" }}>
                    <div style={{ fontSize: 11, color: "var(--s0-muted-text)", marginBottom: 3 }}>Email (optional)</div>
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={e => setInviteEmail(e.target.value)}
                      placeholder="colleague@company.com"
                      onKeyDown={e => e.key === "Enter" && createInvite()}
                      style={{
                        width: "100%", padding: "7px 10px", borderRadius: 6,
                        border: "1px solid var(--s0-border)", background: "var(--s0-surface)",
                        color: "var(--s0-text)", fontSize: 12,
                      }}
                    />
                  </div>
                  <div style={{ flex: "0 0 130px" }}>
                    <div style={{ fontSize: 11, color: "var(--s0-muted-text)", marginBottom: 3 }}>Role</div>
                    <select
                      value={inviteRole}
                      onChange={e => setInviteRole(e.target.value)}
                      style={{
                        width: "100%", padding: "7px 8px", borderRadius: 6,
                        border: "1px solid var(--s0-border)", background: "var(--s0-surface)",
                        color: "var(--s0-text)", fontSize: 12,
                      }}
                    >
                      <option value="admin">Admin</option>
                      <option value="developer">Developer</option>
                      <option value="auditor">Auditor</option>
                      <option value="member">Member</option>
                    </select>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      onClick={createInvite}
                      disabled={inviteBusy}
                      style={{
                        padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 500,
                        background: inviteBusy ? "var(--s0-border)" : "var(--s0-accent)",
                        color: "var(--s0-accent)", border: "none",
                        cursor: inviteBusy ? "not-allowed" : "pointer",
                      }}
                    >
                      {inviteBusy ? "Generating…" : "Generate Link"}
                    </button>
                    <button
                      onClick={() => { setShowInvite(false); setInviteEmail(""); setInviteErr(null); }}
                      style={{
                        padding: "7px 10px", borderRadius: 6, fontSize: 12,
                        background: "transparent", color: "var(--s0-muted-text)",
                        border: "1px solid var(--s0-border)", cursor: "pointer",
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            {inviteLink && (
              <div style={{
                background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)",
                borderRadius: 8, padding: "12px 14px",
              }}>
                <div style={{ fontSize: 11, color: "var(--s0-accent-text)", fontWeight: 600, marginBottom: 6 }}>
                  <Link2 size={11} style={{ display: "inline", marginRight: 4 }} />
                  Invite link generated — share this with the invitee:
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <code style={{
                    flex: 1, background: "var(--s0-surface)", border: "1px solid var(--s0-border)",
                    borderRadius: 6, padding: "7px 10px", fontSize: 11, fontFamily: "monospace",
                    color: "var(--s0-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {inviteLink}
                  </code>
                  <button
                    onClick={copyInviteLink}
                    style={{
                      display: "flex", alignItems: "center", gap: 5,
                      padding: "7px 12px", borderRadius: 6, fontSize: 12,
                      background: copied ? "#16a34a" : "var(--s0-accent)",
                      color: "var(--s0-accent)", border: "none", cursor: "pointer", whiteSpace: "nowrap",
                    }}
                  >
                    <Copy size={12} /> {copied ? "Copied!" : "Copy"}
                  </button>
                  <button
                    onClick={() => { setInviteLink(null); setShowInvite(false); }}
                    style={{
                      padding: "7px 10px", borderRadius: 6, fontSize: 12,
                      background: "transparent", color: "var(--s0-muted-text)",
                      border: "1px solid var(--s0-border)", cursor: "pointer",
                    }}
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Support view — agents & approvals (read-only, audited) */}
          <div style={{ marginTop: 18, borderTop: "1px solid var(--s0-border)", paddingTop: 14 }}>
            <button onClick={toggleSupport}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 7, fontSize: 12, fontWeight: 500, background: "var(--s0-bg)", color: "var(--s0-text)", border: "1px solid var(--s0-border)", cursor: "pointer" }}>
              {supportOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <LifeBuoy size={13} style={{ color: "var(--s0-accent-text)" }} /> Support view — Agents &amp; Approvals
            </button>

            {supportOpen && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 11, color: "var(--s0-muted-text)", marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                  <AlertTriangle size={12} style={{ color: "#ca8a04" }} />
                  Read-only cross-org view for support. Every access is recorded in <em>{org.name}</em>'s audit log.
                </div>
                {supportErr && <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 8 }}>{supportErr}</div>}
                {supportLoading ? (
                  <div style={{ color: "var(--s0-muted-text)", fontSize: 13, padding: "10px 0" }}>Loading…</div>
                ) : (
                  <>
                    {/* Agents */}
                    <strong style={{ fontSize: 12, color: "var(--s0-muted-text)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Agents ({agents.length})</strong>
                    {agents.length === 0 ? (
                      <div style={{ color: "var(--s0-muted-text)", fontSize: 12, padding: "6px 0 12px" }}>No agents in this org.</div>
                    ) : (
                      <table style={{ width: "100%", borderCollapse: "collapse", margin: "8px 0 16px", fontSize: 13 }}>
                        <thead><tr style={{ color: "var(--s0-muted-text)", textAlign: "left" }}>
                          {["Agent","Mode","Status","Last action","Created"].map(h => (
                            <th key={h} style={{ padding: "4px 8px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                          ))}
                        </tr></thead>
                        <tbody>
                          {agents.map(a => (
                            <tr key={a.id} style={{ borderTop: "1px solid var(--s0-border)" }}>
                              <td style={{ padding: "8px" }}>
                                <div style={{ fontWeight: 500 }}>{a.display_name}</div>
                                <div style={{ fontSize: 11, color: "var(--s0-muted-text)" }}>{a.slug}</div>
                              </td>
                              <td style={{ padding: "8px", color: "var(--s0-muted-text)", fontSize: 12 }}>{a.mode}</td>
                              <td style={{ padding: "8px" }}><Badge label={a.is_active ? "active" : "disabled"} color={a.is_active ? "#16a34a" : "#ef4444"} /></td>
                              <td style={{ padding: "8px", color: "var(--s0-muted-text)", fontSize: 12 }}>{fmtDate(a.last_action_at)}</td>
                              <td style={{ padding: "8px", color: "var(--s0-muted-text)", fontSize: 12 }}>{fmtDate(a.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {/* Approvals */}
                    <strong style={{ fontSize: 12, color: "var(--s0-muted-text)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Approvals ({approvals.length})</strong>
                    {approvals.length === 0 ? (
                      <div style={{ color: "var(--s0-muted-text)", fontSize: 12, padding: "6px 0" }}>No approval requests in this org.</div>
                    ) : (
                      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8, fontSize: 13 }}>
                        <thead><tr style={{ color: "var(--s0-muted-text)", textAlign: "left" }}>
                          {["Action","Subject","Status","Created"].map(h => (
                            <th key={h} style={{ padding: "4px 8px", fontWeight: 500, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                          ))}
                        </tr></thead>
                        <tbody>
                          {approvals.map(ap => (
                            <tr key={ap.id} style={{ borderTop: "1px solid var(--s0-border)" }}>
                              <td style={{ padding: "8px", fontFamily: "monospace", fontSize: 12 }}>{ap.action}</td>
                              <td style={{ padding: "8px", color: "var(--s0-muted-text)", fontSize: 12 }}>{ap.subject_type}:{ap.subject_id}</td>
                              <td style={{ padding: "8px" }}><Badge label={ap.status} color={APPROVAL_COLORS[ap.status] || "var(--s0-muted-text)"} /></td>
                              <td style={{ padding: "8px", color: "var(--s0-muted-text)", fontSize: 12 }}>{fmtDate(ap.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Delete org */}
          <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
            {confirmDelete ? (
              <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <AlertTriangle size={14} style={{ color: "#ef4444" }} />
                Delete "{org.name}"?
                <button onClick={deleteOrg} disabled={deleting}
                  style={{ background: "#ef4444", color: "var(--s0-accent)", border: "none", borderRadius: 6, padding: "4px 12px", cursor: "pointer", fontSize: 13 }}>
                  {deleting ? "Deleting…" : "Confirm"}
                </button>
                <button onClick={() => setConfirmDelete(false)}
                  style={{ background: "none", border: "1px solid var(--s0-border)", borderRadius: 6, padding: "4px 12px", cursor: "pointer", color: "var(--s0-text)", fontSize: 13 }}>
                  Cancel
                </button>
              </span>
            ) : (
              <button onClick={() => setConfirmDelete(true)}
                style={{ background: "none", border: "1px solid #ef4444", color: "#ef4444", borderRadius: 6, padding: "5px 14px", cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
                <Trash2 size={13} /> Delete Org
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── User row ──────────────────────────────────────────────────────────────────

function UserRow({ user, onRefresh }: { user: AdminUser; onRefresh: () => void }) {
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function toggle(field: "is_active" | "is_superadmin") {
    setSaving(true);
    try {
      await api.patch(`/api/v1/admin/users/${user.user_id}`, { [field]: !user[field] });
      onRefresh();
    } catch (e: any) {
      setErr(e.message || "Failed to update");
    } finally { setSaving(false); }
  }

  async function saveName(name: string) {
    await api.patch(`/api/v1/admin/users/${user.user_id}`, { display_name: name });
    onRefresh();
  }

  const row: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 1.2fr",
    alignItems: "center",
    gap: 12,
    padding: "12px 18px",
    borderBottom: "1px solid var(--s0-border)",
    fontSize: 13,
  };

  return (
    <div style={row}>
      <div>
        <div style={{ fontWeight: 500, display: "flex", alignItems: "center", gap: 6 }}>
          <EditableText value={user.display_name || user.email} onSave={saveName} />
          {user.is_superadmin && <Crown size={13} style={{ color: "#b45309" }} />}
        </div>
        <div style={{ fontSize: 11, color: "var(--s0-muted-text)" }}>{user.email}</div>
        {err && <div style={{ color: "#ef4444", fontSize: 11, marginTop: 2 }}>{err}</div>}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {user.orgs.slice(0, 3).map(o => (
          <span key={o.org_id} style={{ fontSize: 11, background: "var(--s0-bg)", border: "1px solid var(--s0-border)", borderRadius: 6, padding: "2px 6px" }}>
            {o.org_name} <span style={{ color: ROLE_COLORS[o.seat_role] || "var(--s0-muted-text)" }}>({o.seat_role})</span>
          </span>
        ))}
        {user.orgs.length > 3 && <span style={{ fontSize: 11, color: "var(--s0-muted-text)" }}>+{user.orgs.length - 3}</span>}
        {user.orgs.length === 0 && <span style={{ fontSize: 11, color: "var(--s0-muted-text)" }}>No orgs</span>}
      </div>

      <div style={{ color: "var(--s0-muted-text)", fontSize: 12 }}>{fmtDate(user.created_at)}</div>
      <div style={{ color: "var(--s0-muted-text)", fontSize: 12 }}>{fmtDate(user.last_login_at)}</div>

      {/* Active toggle */}
      <div>
        <button onClick={() => toggle("is_active")} disabled={saving} title={user.is_active ? "Deactivate" : "Activate"}
          style={{ display: "flex", alignItems: "center", gap: 5, background: "none", border: `1px solid ${user.is_active ? "#16a34a" : "#ef4444"}`, borderRadius: 6, padding: "4px 10px", cursor: "pointer", color: user.is_active ? "#16a34a" : "#ef4444", fontSize: 12 }}>
          {user.is_active ? <UserCheck size={13} /> : <UserX size={13} />}
          {user.is_active ? "Active" : "Inactive"}
        </button>
      </div>

      {/* Superadmin toggle */}
      <div>
        <button onClick={() => toggle("is_superadmin")} disabled={saving} title={user.is_superadmin ? "Revoke super admin" : "Grant super admin"}
          style={{ display: "flex", alignItems: "center", gap: 5, background: "none", border: `1px solid ${user.is_superadmin ? "#b45309" : "var(--s0-border)"}`, borderRadius: 6, padding: "4px 10px", cursor: "pointer", color: user.is_superadmin ? "#b45309" : "var(--s0-muted-text)", fontSize: 12 }}>
          <Crown size={13} />
          {user.is_superadmin ? "Super Admin" : "Make Admin"}
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SuperAdmin() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"orgs" | "users">("orgs");
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showCreateOrg, setShowCreateOrg] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgPlan, setNewOrgPlan] = useState("free");
  const [createOrgBusy, setCreateOrgBusy] = useState(false);
  const [createOrgErr, setCreateOrgErr] = useState<string | null>(null);

  // Guard — redirect non-superadmins
  useEffect(() => {
    if (me && !me.is_superadmin) navigate("/", { replace: true });
  }, [me, navigate]);

  const loadOrgs = useCallback(async () => {
    try {
      const data = await api.get<AdminOrg[]>("/api/v1/admin/orgs");
      setOrgs(data);
    } catch (e: any) { setErr(e.message || "Failed to load orgs"); }
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      const data = await api.get<AdminUser[]>("/api/v1/admin/users");
      setUsers(data);
    } catch (e: any) { setErr(e.message || "Failed to load users"); }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    await Promise.all([loadOrgs(), loadUsers()]);
    setLoading(false);
  }, [loadOrgs, loadUsers]);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleCreateOrg() {
    if (!newOrgName.trim()) return;
    setCreateOrgBusy(true);
    setCreateOrgErr(null);
    try {
      await api.post("/api/v1/admin/orgs", { name: newOrgName.trim(), plan: newOrgPlan });
      setNewOrgName("");
      setNewOrgPlan("free");
      setShowCreateOrg(false);
      await refresh();
    } catch (e: any) {
      setCreateOrgErr(e.message || "Failed to create org");
    } finally {
      setCreateOrgBusy(false);
    }
  }

  if (!me?.is_superadmin) return null;

  const filteredOrgs = orgs.filter(o =>
    o.name.toLowerCase().includes(search.toLowerCase()) ||
    o.slug.toLowerCase().includes(search.toLowerCase())
  );
  const filteredUsers = users.filter(u =>
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    (u.display_name || "").toLowerCase().includes(search.toLowerCase())
  );

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 500,
    background: active ? "var(--s0-accent-text)" : "none",
    color: active ? "#fff" : "var(--s0-muted-text)",
  });

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 28 }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, background: "linear-gradient(135deg,#b45309,#92400e)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Shield size={22} color="#fff" />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>Super Admin</h1>
          <p style={{ margin: 0, fontSize: 13, color: "var(--s0-muted-text)" }}>
            Platform-wide org and user management
          </p>
        </div>
        <button onClick={refresh} disabled={loading} title="Refresh"
          style={{ marginLeft: "auto", background: "none", border: "1px solid var(--s0-border)", borderRadius: 8, padding: "8px 14px", cursor: "pointer", color: "var(--s0-muted-text)", display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {/* Stats bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 28 }}>
        {[
          { label: "Total Orgs", value: orgs.length, icon: <Building2 size={18} /> },
          { label: "Total Users", value: users.length, icon: <Users size={18} /> },
          { label: "Active Users", value: users.filter(u => u.is_active).length, icon: <UserCheck size={18} /> },
          { label: "Super Admins", value: users.filter(u => u.is_superadmin).length, icon: <Crown size={18} /> },
        ].map(s => (
          <div key={s.label} style={{ background: "var(--s0-surface)", border: "1px solid var(--s0-border)", borderRadius: 10, padding: "16px 20px", display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ color: "var(--s0-accent-text)" }}>{s.icon}</span>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{s.value}</div>
              <div style={{ fontSize: 12, color: "var(--s0-muted-text)" }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs + search */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 6, background: "var(--s0-surface)", border: "1px solid var(--s0-border)", borderRadius: 10, padding: 4 }}>
          <button style={tabStyle(tab === "orgs")} onClick={() => setTab("orgs")}>
            <Building2 size={14} style={{ display: "inline", marginRight: 6 }} />
            Orgs ({orgs.length})
          </button>
          <button style={tabStyle(tab === "users")} onClick={() => setTab("users")}>
            <Users size={14} style={{ display: "inline", marginRight: 6 }} />
            Users ({users.length})
          </button>
        </div>
        {tab === "orgs" && (
          <button
            onClick={() => { setShowCreateOrg(s => !s); setCreateOrgErr(null); }}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "7px 14px", borderRadius: 8, fontSize: 13, fontWeight: 500,
              background: "var(--s0-accent)", color: "#fff", border: "none", cursor: "pointer",
            }}
          >
            <Plus size={14} /> New Org
          </button>
        )}
        <input
          placeholder={`Search ${tab}…`}
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            marginLeft: "auto", padding: "8px 14px", borderRadius: 8,
            border: "1px solid var(--s0-border)", background: "var(--s0-surface)",
            color: "var(--s0-text)", fontSize: 13, width: 240,
          }}
        />
      </div>

      {err && (
        <div style={{ color: "#ef4444", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 8, padding: "12px 16px", marginBottom: 16, fontSize: 13 }}>
          {err}
        </div>
      )}

      {/* Create Org form */}
      {showCreateOrg && (
        <div style={{
          background: "var(--s0-surface)", border: "1px solid var(--s0-border)",
          borderRadius: 10, padding: "18px 20px", marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--s0-text)", marginBottom: 14 }}>
            Create New Organization
          </div>
          {createOrgErr && (
            <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 10 }}>{createOrgErr}</div>
          )}
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 200px" }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--s0-muted-text)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Org Name</div>
              <input
                value={newOrgName}
                onChange={e => setNewOrgName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreateOrg()}
                placeholder="Acme Corp"
                style={{
                  width: "100%", padding: "8px 12px", borderRadius: 7,
                  border: "1px solid var(--s0-border)", background: "var(--s0-bg)",
                  color: "var(--s0-text)", fontSize: 13,
                }}
              />
            </div>
            <div style={{ flex: "0 0 150px" }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--s0-muted-text)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Plan</div>
              <select
                value={newOrgPlan}
                onChange={e => setNewOrgPlan(e.target.value)}
                style={{
                  width: "100%", padding: "8px 12px", borderRadius: 7,
                  border: "1px solid var(--s0-border)", background: "var(--s0-bg)",
                  color: "var(--s0-text)", fontSize: 13,
                }}
              >
                <option value="free">Free</option>
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={handleCreateOrg}
                disabled={createOrgBusy || !newOrgName.trim()}
                style={{
                  padding: "8px 18px", borderRadius: 7, fontSize: 13, fontWeight: 500,
                  background: createOrgBusy || !newOrgName.trim() ? "var(--s0-border)" : "var(--s0-accent)",
                  color: "var(--s0-accent)", border: "none",
                  cursor: createOrgBusy || !newOrgName.trim() ? "not-allowed" : "pointer",
                }}
              >
                {createOrgBusy ? "Creating…" : "Create"}
              </button>
              <button
                onClick={() => { setShowCreateOrg(false); setNewOrgName(""); setCreateOrgErr(null); }}
                style={{
                  padding: "8px 14px", borderRadius: 7, fontSize: 13,
                  background: "transparent", color: "var(--s0-muted-text)",
                  border: "1px solid var(--s0-border)", cursor: "pointer",
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: "var(--s0-muted-text)", padding: 40, textAlign: "center" }}>Loading…</div>
      ) : tab === "orgs" ? (
        <div>
          {filteredOrgs.length === 0
            ? <div style={{ color: "var(--s0-muted-text)", padding: 40, textAlign: "center" }}>No orgs found</div>
            : filteredOrgs.map(org => <OrgRow key={org.org_id} org={org} onRefresh={refresh} />)
          }
        </div>
      ) : (
        <div style={{ background: "var(--s0-surface)", border: "1px solid var(--s0-border)", borderRadius: 10, overflow: "hidden" }}>
          {/* Header row */}
          <div style={{
            display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 1.2fr",
            gap: 12, padding: "10px 18px",
            borderBottom: "1px solid var(--s0-border)",
            fontSize: 11, fontWeight: 600, color: "var(--s0-muted-text)", textTransform: "uppercase", letterSpacing: "0.05em",
          }}>
            {["User","Orgs","Joined","Last Login","Status","Super Admin"].map(h => <div key={h}>{h}</div>)}
          </div>
          {filteredUsers.length === 0
            ? <div style={{ color: "var(--s0-muted-text)", padding: 40, textAlign: "center" }}>No users found</div>
            : filteredUsers.map(u => <UserRow key={u.user_id} user={u} onRefresh={refresh} />)
          }
        </div>
      )}
    </div>
  );
}
