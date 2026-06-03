import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users, Key, Building2, Plug, Plus, Copy, Trash2, CheckCircle2, ExternalLink,
  Crown, Code2, Eye, User as UserIcon, Activity, ChevronDown, ChevronUp,
  AlertTriangle, RotateCcw, LogOut, X, Pencil, Save,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";
import { useTheme, THEMES, type ThemeId } from "@/lib/theme";
import { Palette, Check } from "lucide-react";

type TabId = "members" | "apikeys" | "sso" | "org" | "profile";

const ROLE_ICONS: Record<string, React.ElementType> = {
  owner: Crown, admin: Crown, developer: Code2, auditor: Eye, member: UserIcon,
};
const ROLE_COLORS: Record<string, string> = {
  owner: "#F59E0B", admin: "var(--s0-accent)", developer: "#10B981", auditor: "#2DD4BF", member: "#94A3B8",
};

export default function SettingsPage() {
  const [tab, setTab] = useState<TabId>("members");

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Organization, members, API keys, identity providers, and profile."
      />
      <div className="px-8 py-6">
        <div className="flex border-b border-ink-800 mb-6 gap-1">
          <TabBtn active={tab === "members"} onClick={() => setTab("members")}
                  icon={<Users className="size-4" />} label="Members" />
          <TabBtn active={tab === "apikeys"} onClick={() => setTab("apikeys")}
                  icon={<Key className="size-4" />} label="API keys" />
          <TabBtn active={tab === "sso"} onClick={() => setTab("sso")}
                  icon={<Plug className="size-4" />} label="Identity providers" />
          <TabBtn active={tab === "org"} onClick={() => setTab("org")}
                  icon={<Building2 className="size-4" />} label="Organization" />
          <TabBtn active={tab === "profile"} onClick={() => setTab("profile")}
                  icon={<Palette className="size-4" />} label="Profile" />
        </div>

        {tab === "members" && <MembersTab />}
        {tab === "apikeys" && <ApiKeysTab />}
        {tab === "sso" && <SsoTab />}
        {tab === "org" && <OrgTab />}
        {tab === "profile" && <ProfileTab />}
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, label }:
  { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm flex items-center gap-2 border-b-2 -mb-px transition
        ${active
          ? "border-accent-500 text-ink-100"
          : "border-transparent text-ink-400 hover:text-ink-200"}`}
    >
      {icon} {label}
    </button>
  );
}

// ── Members tab ────────────────────────────────────────────────────────────
function MembersTab() {
  const qc = useQueryClient();
  const [showInvite, setShowInvite] = useState(false);
  const [inviteRole, setInviteRole] = useState("developer");
  const [inviteEmail, setInviteEmail] = useState("");
  const [freshLink, setFreshLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [editingRole, setEditingRole] = useState<string | null>(null);

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<any>("/api/v1/auth/me"),
  });

  const { data: members = [] } = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<any[]>("/api/v1/org/members"),
  });

  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.patch(`/api/v1/org/members/${userId}`, { seat_role: role }),
    onSuccess: () => {
      setEditingRole(null);
      qc.invalidateQueries({ queryKey: ["org-members"] });
    },
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) => api.del(`/api/v1/org/members/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org-members"] }),
  });

  const { data: invites = [] } = useQuery({
    queryKey: ["invites"],
    queryFn: () => api.get<any[]>("/api/v1/invites"),
  });

  const createInvite = useMutation({
    mutationFn: () => api.post<any>("/api/v1/invites", {
      seat_role: inviteRole,
      email: inviteEmail || null,
    }),
    onSuccess: (r) => {
      const link = `${window.location.origin}/invite?token=${r.token}`;
      setFreshLink(link);
      setInviteEmail("");
      setShowInvite(false);
      qc.invalidateQueries({ queryKey: ["invites"] });
    },
  });

  const revokeInvite = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/invites/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invites"] }),
  });

  function copyLink() {
    if (!freshLink) return;
    navigator.clipboard.writeText(freshLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const pendingInvites = invites.filter((i: any) => !i.used && !i.revoked);

  return (
    <div className="space-y-4">

      {/* Current members */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-800">
          <div className="text-sm font-medium text-ink-50">
            Members <span className="ml-1.5 text-xs text-ink-500 font-normal">{members.length}</span>
          </div>
          <button className="btn-primary text-xs" onClick={() => setShowInvite(s => !s)}>
            <Plus className="size-3.5" /> Invite member
          </button>
        </div>

        <table className="table">
          <thead>
            <tr><th>Member</th><th>Role</th><th>MFA</th><th>Last sign in</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {members.map((m: any) => {
              const RoleIcon = ROLE_ICONS[m.seat_role] || UserIcon;
              const roleColor = ROLE_COLORS[m.seat_role] || "#94A3B8";
              const isEditing = editingRole === m.user_id;
              return (
                <tr key={m.user_id}>
                  <td>
                    <div className="flex items-center gap-2.5">
                      <div className="size-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                        style={{ background: "var(--s0-accent-ring)", color: "var(--s0-accent-text)" }}>
                        {(m.display_name || m.email).charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="text-sm font-medium text-ink-100">{m.display_name || "—"}</div>
                        <div className="text-xs text-ink-500 font-mono">{m.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    {isEditing ? (
                      <select
                        className="input text-xs py-0.5 px-2 h-7"
                        defaultValue={m.seat_role}
                        autoFocus
                        onChange={(e) => {
                          changeRole.mutate({ userId: m.user_id, role: e.currentTarget.value });
                        }}
                        onBlur={() => setEditingRole(null)}
                      >
                        {["owner", "admin", "developer", "auditor", "member"].map(r => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    ) : (
                      <button
                        className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-md hover:opacity-80 transition-opacity"
                        style={{ background: `${roleColor}18`, color: roleColor }}
                        onClick={() => setEditingRole(m.user_id)}
                        title="Click to change role"
                      >
                        <RoleIcon className="size-3" /> {m.seat_role} <Pencil className="size-2.5 opacity-50" />
                      </button>
                    )}
                  </td>
                  <td>
                    {m.mfa_enrolled
                      ? <span className="pill-ok text-[10px]"><CheckCircle2 className="size-3" />enabled</span>
                      : <span className="pill text-[10px] text-ink-500">off</span>}
                  </td>
                  <td className="text-xs text-ink-400">
                    {m.last_login_at ? new Date(m.last_login_at).toLocaleDateString() : "never"}
                  </td>
                  <td>
                    <button
                      className="btn-ghost text-danger-400 text-xs"
                      title="Remove member"
                      onClick={() => {
                        if (confirm(`Remove ${m.email} from this organization?`)) {
                          removeMember.mutate(m.user_id);
                        }
                      }}
                    >
                      <X className="size-3.5" /> Remove
                    </button>
                  </td>
                </tr>
              );
            })}
            {members.length === 0 && (
              <tr><td colSpan={5} className="text-center text-ink-500 py-8 text-xs">
                No members found.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Invite form (slide-in) */}
      {showInvite && (
        <div className="card p-5">
          <div className="text-sm font-medium text-ink-50 mb-4">Invite a team member</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div className="md:col-span-2">
              <label className="label">Email <span className="text-ink-500 font-normal">(optional — leave blank for open link)</span></label>
              <input className="input" type="email" placeholder="colleague@company.com"
                value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} />
            </div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                {me?.is_superadmin && <option value="admin">Admin</option>}
                <option value="developer">Developer</option>
                <option value="auditor">Auditor</option>
                <option value="member">Member</option>
              </select>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-primary" onClick={() => createInvite.mutate()}
              disabled={createInvite.isPending}>
              {createInvite.isPending ? "Generating…" : "Generate invite link"}
            </button>
            <button className="btn-ghost" onClick={() => setShowInvite(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Freshly generated link */}
      {freshLink && (
        <div className="card p-4" style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)" }}>
          <div className="text-xs text-indigo-300 mb-2 font-medium">Invite link generated — share this with your colleague:</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-ink-900 border border-ink-800 rounded-lg p-2.5 text-xs font-mono text-ink-300 truncate">
              {freshLink}
            </code>
            <button className="btn-primary px-3 py-2 text-xs" onClick={copyLink}>
              {copied ? <><CheckCircle2 className="size-3.5" /> Copied</> : <><Copy className="size-3.5" /> Copy</>}
            </button>
          </div>
        </div>
      )}

      {/* Pending invitations — always visible */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-ink-800 flex items-center justify-between">
          <span className="text-sm font-medium text-ink-50">
            Pending invitations
            {pendingInvites.length > 0 && (
              <span className="ml-2 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-accent-600/20 text-accent-400">
                {pendingInvites.length}
              </span>
            )}
          </span>
          <span className="text-xs text-ink-500">Invited but not yet accepted</span>
        </div>

        {pendingInvites.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-ink-500">
            No pending invitations — everyone who was invited has joined.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Invited by</th>
                <th>Invited</th>
                <th>Expires</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {pendingInvites.map((i: any) => {
                const expiresAt = new Date(i.expires_at);
                const now = new Date();
                const hoursLeft = Math.round((expiresAt.getTime() - now.getTime()) / 3_600_000);
                const expiringSoon = hoursLeft < 24;
                return (
                  <tr key={i.invite_id}>
                    <td>
                      {i.email
                        ? <span className="text-xs font-mono text-ink-200">{i.email}</span>
                        : <span className="text-xs text-ink-500 italic">open link (no email set)</span>}
                    </td>
                    <td><span className="pill-info">{i.seat_role}</span></td>
                    <td className="text-xs text-ink-400">
                      {i.invited_by_name || i.invited_by_email || <span className="text-ink-600">—</span>}
                    </td>
                    <td className="text-xs text-ink-400">
                      {new Date(i.created_at).toLocaleDateString()}
                    </td>
                    <td className={`text-xs ${expiringSoon ? "text-warn-400 font-medium" : "text-ink-400"}`}>
                      {expiringSoon
                        ? `${hoursLeft}h left`
                        : expiresAt.toLocaleDateString()}
                    </td>
                    <td>
                      <button
                        className="btn-ghost text-danger-400 text-xs"
                        onClick={() => revokeInvite.mutate(i.invite_id)}
                        disabled={revokeInvite.isPending}
                      >
                        <Trash2 className="size-3.5" /> Revoke
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const SCOPES = [
  { id: "audit.read",       desc: "Read audit events — needed for SIEM polling" },
  { id: "decisions.check",  desc: "Submit decision check requests" },
  { id: "agents.read",      desc: "Read agent list and details" },
  { id: "policies.read",    desc: "Read policy list and details" },
  { id: "tools.read",       desc: "Read tool registry" },
];

// ── API Keys tab ───────────────────────────────────────────────────────────
function ApiKeysTab() {
  const qc = useQueryClient();
  const [newKeyName, setNewKeyName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["audit.read"]);
  const [freshSecret, setFreshSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [siemOpen, setSiemOpen] = useState(false);

  const { data = [] } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<any[]>("/api/v1/api-keys"),
  });

  const create = useMutation({
    mutationFn: () => api.post<any>("/api/v1/api-keys", {
      name: newKeyName,
      scopes: selectedScopes,
    }),
    onSuccess: (r) => {
      setFreshSecret(r.secret);
      setNewKeyName("");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  function toggleScope(s: string) {
    setSelectedScopes(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }

  function copySecret() {
    if (!freshSecret) return;
    navigator.clipboard.writeText(freshSecret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-4">

      {/* ── SIEM / Splunk integration guide ── */}
      <div className="card overflow-hidden">
        <button
          onClick={() => setSiemOpen(o => !o)}
          className="w-full flex items-center justify-between px-5 py-4 text-left"
          style={{ borderBottom: siemOpen ? "1px solid rgba(148,163,184,0.08)" : "none" }}
        >
          <div className="flex items-center gap-3">
            <div className="size-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)" }}>
              <Activity className="size-4" style={{ color: "var(--s0-accent-text)" }} />
            </div>
            <div>
              <div className="text-sm font-medium text-ink-50">SIEM integration — Splunk, Datadog, Elastic, etc.</div>
              <div className="text-xs text-ink-400">Pull audit events every 5 minutes using a static API key</div>
            </div>
          </div>
          {siemOpen
            ? <ChevronUp className="size-4 text-ink-500" />
            : <ChevronDown className="size-4 text-ink-500" />}
        </button>

        {siemOpen && (
          <div className="px-5 pb-5 space-y-5 pt-4">
            <p className="text-sm text-ink-300 leading-relaxed">
              Create an API key with <code className="text-xs">audit.read</code> scope below,
              then configure your SIEM to poll <code className="text-xs">GET /api/v1/audit/events</code>.
              Use the <code className="text-xs">since_sequence</code> cursor to fetch only new events each run.
            </p>

            <div>
              <div className="text-xs font-semibold text-ink-300 uppercase tracking-wider mb-2">Polling endpoint</div>
              <div className="rounded-lg p-3 font-mono text-xs text-ink-300"
                style={{ background: "#0A0F1A", border: "1px solid rgba(148,163,184,0.1)" }}>
                GET https://kynara.ai/api/v1/audit/events<br />
                &nbsp;&nbsp;?since_sequence=&#123;last_sequence&#125;<br />
                &nbsp;&nbsp;&amp;limit=500<br />
                Authorization: Bearer sk_live_…
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold text-ink-300 uppercase tracking-wider mb-2">Response shape</div>
              <div className="rounded-lg p-3 font-mono text-xs text-ink-400"
                style={{ background: "#0A0F1A", border: "1px solid rgba(148,163,184,0.1)" }}>
                {"[{\n"
                + '  "sequence": 1042,       // ← save this as your next cursor\n'
                + '  "ts": "2026-04-26T14:00:01Z",\n'
                + '  "event_type": "policy.decision",\n'
                + '  "actor": "agent:f3a…",\n'
                + '  "resource_type": "file",\n'
                + '  "outcome": "allow",\n'
                + '  "entry_hash": "a3f9…"   // tamper-evidence\n'
                + "}]"}
              </div>
            </div>

            <div className="grid md:grid-cols-3 gap-3">
              {[
                {
                  tool: "Splunk",
                  steps: [
                    'Install "Splunk Add-on for REST API" or use the Modular Input SDK',
                    "Create an input with URL: https://kynara.ai/api/v1/audit/events",
                    "Add header Authorization: Bearer <your-api-key>",
                    "Set interval to 300 s (5 min) and sourcetype kynara:audit",
                    "Use a KV store checkpoint to track since_sequence between runs",
                  ],
                },
                {
                  tool: "Datadog",
                  steps: [
                    "Use the Datadog HTTP Log Intake or a custom Lambda/Cloud Run forwarder",
                    "Schedule a function every 5 min, store cursor in SSM/Secret Manager",
                    "Fetch from Kynara, POST each event to https://http-intake.logs.datadoghq.com/api/v2/logs",
                    "Tag with source:kynara and service:audit",
                  ],
                },
                {
                  tool: "Elastic / OpenSearch",
                  steps: [
                    "Use Filebeat HTTP JSON input or a Logstash pipeline",
                    "Point the url to /api/v1/audit/events?since_sequence=…",
                    "Set schedule: every 5m and persist the cursor in the registry",
                    "Map outcome→labels.outcome and entry_hash to a keyword field",
                  ],
                },
              ].map(({ tool, steps }) => (
                <div key={tool} className="rounded-lg p-4"
                  style={{ background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.08)" }}>
                  <div className="text-sm font-semibold text-ink-50 mb-3">{tool}</div>
                  <ol className="space-y-2">
                    {steps.map((s, i) => (
                      <li key={i} className="flex gap-2 text-xs text-ink-400 leading-relaxed">
                        <span className="shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5"
                          style={{ background: "var(--s0-accent-ring)", color: "var(--s0-accent-text)" }}>
                          {i + 1}
                        </span>
                        {s}
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>

            <div className="rounded-lg px-4 py-3 text-xs text-ink-300 leading-relaxed"
              style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(4,120,87,0.2)" }}>
              <strong className="text-ok-400">Cursor pattern:</strong> On each poll, save the highest{" "}
              <code>sequence</code> value you received. Pass it as{" "}
              <code>since_sequence=&lt;value&gt;</code> on the next request. Events are returned
              oldest-first in this mode so you can append them in order. If you receive 500 events,
              immediately poll again — more may be waiting.
            </div>
          </div>
        )}
      </div>

      {/* ── Create key form ── */}
      <div className="card p-5">
        <div className="text-sm font-medium mb-1">Create API key</div>
        <p className="text-xs text-ink-400 mb-4">
          Keys are shown exactly once. The server stores only a SHA-256 hash — never the secret.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Key name</label>
            <input className="input" value={newKeyName}
                   placeholder="splunk-audit-reader"
                   onChange={(e) => setNewKeyName(e.target.value)} />
          </div>
          <div>
            <label className="label">Scopes</label>
            <div className="space-y-2 mt-1">
              {SCOPES.map(s => (
                <label key={s.id} className="flex items-start gap-2.5 cursor-pointer group">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-indigo-500"
                    checked={selectedScopes.includes(s.id)}
                    onChange={() => toggleScope(s.id)}
                  />
                  <div>
                    <span className="text-xs font-mono text-ink-100">{s.id}</span>
                    <span className="text-xs text-ink-500 ml-2">{s.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>
        <button className="btn-primary" disabled={!newKeyName || selectedScopes.length === 0}
                onClick={() => create.mutate()}>
          <Plus className="size-4" /> Create key
        </button>

        {freshSecret && (
          <div className="mt-4 rounded-lg p-3" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
            <div className="text-xs text-warn-300 mb-2 font-medium">
              Copy this now — you won't see it again.
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-ink-900 border border-ink-800 rounded p-2 text-xs font-mono break-all">
                {freshSecret}
              </code>
              <button className="btn-ghost shrink-0"
                      onClick={copySecret}>
                {copied ? <CheckCircle2 className="size-4 text-ok-400" /> : <Copy className="size-4" />}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card overflow-hidden">
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Prefix</th><th>Scopes</th><th>Created</th><th>Last used</th><th /></tr>
          </thead>
          <tbody>
            {data.map((k) => (
              <tr key={k.id}>
                <td className="text-sm font-medium">{k.name}</td>
                <td className="text-xs font-mono text-ink-400">{k.prefix}…</td>
                <td>
                  <div className="flex flex-wrap gap-1">
                    {(k.scopes || []).map((s: string) => (
                      <span key={s} className="pill font-mono text-[10px]">{s}</span>
                    ))}
                  </div>
                </td>
                <td className="text-xs text-ink-400">{new Date(k.created_at).toLocaleDateString()}</td>
                <td className="text-xs text-ink-400">
                  {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "never"}
                </td>
                <td>
                  <button className="btn-ghost text-danger-400" onClick={() => revoke.mutate(k.id)}>
                    <Trash2 className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
            {!data.length && (
              <tr><td colSpan={6} className="text-center text-ink-500 py-8 text-xs">
                No API keys yet.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── SSO tab ────────────────────────────────────────────────────────────────
function SsoTab() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<any | null>(null);

  const { data = [] } = useQuery({
    queryKey: ["sso-connections"],
    queryFn: () => api.get<any[]>("/api/v1/sso/connections"),
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch<any>(`/api/v1/sso/connections/${id}`, { is_enabled: enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sso-connections"] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.del<any>(`/api/v1/sso/connections/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sso-connections"] }); setEditing(null); },
  });

  const base = (import.meta.env.VITE_API_BASE || window.location.origin).replace(/\/$/, "");
  const metadataUrl = `${base}/api/v1/auth/sso/saml/metadata`;

  return (
    <>
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div className="text-sm text-ink-300">
            Configure SAML 2.0 or OIDC identity providers to let employees sign in
            with your corporate IdP. SCIM 2.0 provisioning is available on Enterprise plans.
          </div>
          <Link to="/app/settings/sso/new" className="btn-primary">
            <Plus className="size-4" /> Add provider
          </Link>
        </div>

        <div className="card overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th>Provider</th><th>Protocol</th><th>Domain</th>
                <th>Created</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr
                  key={c.id}
                  className="cursor-pointer hover:bg-white/[0.02] transition-colors"
                  onClick={() => setEditing(c)}
                >
                  <td className="font-medium" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="flex items-center gap-2 text-sm text-left hover:text-accent-400 transition-colors"
                      onClick={() => setEditing(c)}
                    >
                      <Plug className="size-4 text-accent-500 shrink-0" /> {c.provider}
                    </button>
                  </td>
                  <td><span className="pill-info font-mono">{c.protocol}</span></td>
                  <td className="text-xs font-mono text-ink-400">{c.domain || "—"}</td>
                  <td className="text-xs text-ink-400">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      className="flex items-center gap-1.5 text-xs"
                      title={c.is_enabled ? "Click to disable" : "Click to enable"}
                      onClick={() => toggle.mutate({ id: c.id, enabled: !c.is_enabled })}
                      disabled={toggle.isPending}
                    >
                      {c.is_enabled
                        ? <span className="pill-ok"><CheckCircle2 className="size-3" /> active</span>
                        : <span className="pill-neutral">disabled</span>}
                    </button>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <button
                        className="btn-ghost p-1" title="Edit"
                        onClick={() => setEditing(c)}
                      >
                        <Pencil className="size-3.5" />
                      </button>
                      <button
                        className="btn-ghost text-danger-400 p-1" title="Delete"
                        onClick={() => {
                          if (confirm(`Delete "${c.provider}" SSO connection? This cannot be undone.`)) {
                            remove.mutate(c.id);
                          }
                        }}
                        disabled={remove.isPending}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!data.length && (
                <tr>
                  <td colSpan={6} className="text-center text-ink-500 py-8 text-xs">
                    No SSO providers configured. Users will sign in with password + optional MFA.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="card p-5">
          <div className="text-sm font-medium mb-2 flex items-center gap-2">
            <ExternalLink className="size-4 text-accent-500" /> Service Provider metadata
          </div>
          <p className="text-xs text-ink-400 mb-3">
            Share this metadata URL with your IdP admin. For SAML, this contains
            the SP ACS URL and signing certificate.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 block bg-ink-900 border border-ink-800 rounded p-3 text-xs font-mono break-all">
              {metadataUrl}
            </code>
            <button
              className="btn-ghost shrink-0"
              onClick={() => navigator.clipboard.writeText(metadataUrl)}
              title="Copy"
            >
              <Copy className="size-4" />
            </button>
          </div>
        </div>
      </div>

      {editing && (
        <SsoEditModal
          connection={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { qc.invalidateQueries({ queryKey: ["sso-connections"] }); setEditing(null); }}
          onDeleted={() => { remove.mutate(editing.id); }}
        />
      )}
    </>
  );
}

function SsoEditModal({ connection, onClose, onSaved, onDeleted }: {
  connection: any;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const [form, setForm] = useState({
    provider:                  connection.provider ?? "",
    domain:                    connection.domain ?? "",
    issuer:                    connection.issuer ?? "",
    client_id:                 connection.client_id ?? "",
    client_secret:             "",   // never pre-filled for security
    idp_entity_id:             connection.idp_entity_id ?? "",
    idp_sso_url:               connection.idp_sso_url ?? "",
    idp_x509:                  connection.idp_x509_cert ?? "",
    attribute_mapping_email:   connection.attribute_mapping_email ?? "email",
    attribute_mapping_name:    connection.attribute_mapping_name ?? "name",
    attribute_mapping_groups:  connection.attribute_mapping_groups ?? "groups",
  });

  const save = useMutation({
    mutationFn: () => api.put<any>(`/api/v1/sso/connections/${connection.id}`, {
      ...form,
      protocol: connection.protocol,
    }),
    onSuccess: onSaved,
  });

  const isOidc = connection.protocol === "oidc";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-xl rounded-2xl flex flex-col max-h-[90vh]"
        style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,0.12)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 shrink-0"
          style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
          <div>
            <div className="font-semibold text-ink-50 flex items-center gap-2">
              <Plug className="size-4 text-accent-500" />
              {connection.provider}
            </div>
            <div className="text-xs text-ink-400 mt-0.5 font-mono">{connection.protocol.toUpperCase()} · ID: {connection.id.slice(0, 8)}…</div>
          </div>
          <button onClick={onClose} className="text-ink-500 hover:text-ink-200 transition-colors">
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          <SsoField label="Display name / provider">
            <input className="input" value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })} />
          </SsoField>

          <SsoField label="Email domain (users with this domain are routed here)">
            <input className="input font-mono" placeholder="acme.com" value={form.domain}
              onChange={(e) => setForm({ ...form, domain: e.target.value })} />
          </SsoField>

          {isOidc ? (
            <>
              <SsoField label="Issuer URL">
                <input className="input font-mono" value={form.issuer}
                  onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
              </SsoField>
              <div className="grid grid-cols-2 gap-3">
                <SsoField label="Client ID">
                  <input className="input font-mono" value={form.client_id}
                    onChange={(e) => setForm({ ...form, client_id: e.target.value })} />
                </SsoField>
                <SsoField label={connection.client_secret_set ? "Client secret (leave blank to keep)" : "Client secret"}>
                  <input className="input font-mono" type="password"
                    placeholder={connection.client_secret_set ? "••••••••" : "Enter secret"}
                    value={form.client_secret}
                    onChange={(e) => setForm({ ...form, client_secret: e.target.value })} />
                </SsoField>
              </div>
            </>
          ) : (
            <>
              <SsoField label="IdP Entity ID">
                <input className="input font-mono" value={form.idp_entity_id}
                  onChange={(e) => setForm({ ...form, idp_entity_id: e.target.value })} />
              </SsoField>
              <SsoField label="IdP SSO URL">
                <input className="input font-mono" value={form.idp_sso_url}
                  onChange={(e) => setForm({ ...form, idp_sso_url: e.target.value })} />
              </SsoField>
              <SsoField label="X.509 signing certificate">
                <textarea className="input font-mono text-xs min-h-[100px]"
                  value={form.idp_x509}
                  onChange={(e) => setForm({ ...form, idp_x509: e.target.value })} />
              </SsoField>
            </>
          )}

          <div>
            <div className="text-xs font-medium text-ink-300 mb-2">Attribute mapping</div>
            <div className="grid grid-cols-3 gap-3">
              <SsoField label="Email claim">
                <input className="input font-mono" value={form.attribute_mapping_email}
                  onChange={(e) => setForm({ ...form, attribute_mapping_email: e.target.value })} />
              </SsoField>
              <SsoField label="Name claim">
                <input className="input font-mono" value={form.attribute_mapping_name}
                  onChange={(e) => setForm({ ...form, attribute_mapping_name: e.target.value })} />
              </SsoField>
              <SsoField label="Groups claim">
                <input className="input font-mono" value={form.attribute_mapping_groups}
                  onChange={(e) => setForm({ ...form, attribute_mapping_groups: e.target.value })} />
              </SsoField>
            </div>
          </div>

          {save.isError && (
            <div className="rounded-lg px-3 py-2 text-xs text-danger-400"
              style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(190,18,60,0.25)" }}>
              Failed to save — check all required fields and try again.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 flex items-center justify-between shrink-0"
          style={{ borderTop: "1px solid rgba(148,163,184,0.08)" }}>
          <button
            className="btn-ghost text-danger-400 flex items-center gap-1.5 text-sm"
            onClick={() => {
              if (confirm(`Delete "${connection.provider}"? This cannot be undone.`)) onDeleted();
            }}
          >
            <Trash2 className="size-3.5" /> Delete connection
          </button>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button
              className="btn-primary"
              onClick={() => save.mutate()}
              disabled={save.isPending}
            >
              <Save className="size-4" />
              {save.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SsoField({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="label">{label}</label>{children}</div>;
}

// ── Danger zone modal ──────────────────────────────────────────────────────
type DangerAction = "rotate-keys" | "revoke-sessions" | "delete-org" | null;

function DangerModal({
  action, orgName, onClose,
}: { action: DangerAction; orgName: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      if (action === "rotate-keys")
        return api.post<any>("/api/v1/org/rotate-api-keys", {});
      if (action === "revoke-sessions")
        return api.post<any>("/api/v1/org/revoke-sessions", {});
      if (action === "delete-org")
        return api.del<any>("/api/v1/org");
    },
    onSuccess: () => {
      setDone(true);
      if (action === "rotate-keys") qc.invalidateQueries({ queryKey: ["api-keys"] });
      if (action === "delete-org") {
        // Force sign-out after org deletion
        setTimeout(() => {
          localStorage.removeItem("kynara_access");
          localStorage.removeItem("kynara_refresh");
          window.location.href = "/login";
        }, 2000);
      }
    },
  });

  if (!action) return null;

  const meta: Record<NonNullable<DangerAction>, {
    icon: React.ElementType; title: string; desc: string;
    confirmLabel: string; requiresTyping?: boolean; iconColor: string; iconBg: string;
  }> = {
    "rotate-keys": {
      icon: RotateCcw,
      iconColor: "#F59E0B", iconBg: "rgba(245,158,11,0.12)",
      title: "Rotate all API keys",
      desc: "All active API keys for this organization will be immediately revoked. Any services using them will stop authenticating until new keys are issued.",
      confirmLabel: "Rotate API keys",
    },
    "revoke-sessions": {
      icon: LogOut,
      iconColor: "#F59E0B", iconBg: "rgba(245,158,11,0.12)",
      title: "Revoke all active sessions",
      desc: "Every active browser session across all organization members will be signed out immediately. Users will need to log in again.",
      confirmLabel: "Revoke all sessions",
    },
    "delete-org": {
      icon: AlertTriangle,
      iconColor: "#F43F5E", iconBg: "rgba(244,63,94,0.12)",
      title: "Delete organization",
      desc: `This will permanently delete "${orgName}" and all associated data — agents, policies, audit logs, API keys, and memberships. This cannot be undone.`,
      confirmLabel: "Delete organization",
      requiresTyping: true,
    },
  };

  const m = meta[action];
  const Icon = m.icon;
  const canSubmit = m.requiresTyping ? confirm === orgName : true;
  const isDanger = action === "delete-org";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget && !mutation.isPending) onClose(); }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-7 relative"
        style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,0.12)" }}
      >
        <button
          onClick={onClose}
          disabled={mutation.isPending}
          className="absolute top-4 right-4 text-ink-500 hover:text-ink-300 transition-colors disabled:opacity-40"
        >
          <X className="size-4" />
        </button>

        {done ? (
          <div className="text-center py-4">
            <div
              className="size-14 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)" }}
            >
              <CheckCircle2 className="size-7" style={{ color: "#34D399" }} />
            </div>
            <div className="text-lg font-bold text-ink-50 mb-2">
              {action === "rotate-keys" && "All API keys revoked"}
              {action === "revoke-sessions" && "All sessions revoked"}
              {action === "delete-org" && "Organization deleted"}
            </div>
            <p className="text-sm text-ink-400">
              {action === "delete-org"
                ? "Signing you out…"
                : "The action has been recorded in the audit log."}
            </p>
            {action !== "delete-org" && (
              <button className="btn-primary mt-5" onClick={onClose}>Done</button>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-start gap-4 mb-5">
              <div
                className="size-11 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: m.iconBg }}
              >
                <Icon className="size-5" style={{ color: m.iconColor }} />
              </div>
              <div>
                <div className="font-semibold text-ink-50">{m.title}</div>
                <p className="text-sm text-ink-400 mt-1 leading-relaxed">{m.desc}</p>
              </div>
            </div>

            {m.requiresTyping && (
              <div className="mb-5">
                <label className="label">
                  Type <span className="font-mono text-ink-100">{orgName}</span> to confirm
                </label>
                <input
                  className="input"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder={orgName}
                  autoFocus
                />
              </div>
            )}

            {mutation.isError && (
              <div
                className="rounded-lg px-3 py-2.5 text-xs text-danger-400 mb-4"
                style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(190,18,60,0.25)" }}
              >
                Something went wrong. Please try again.
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button
                className="btn-secondary"
                onClick={onClose}
                disabled={mutation.isPending}
              >
                Cancel
              </button>
              <button
                className={isDanger ? "btn-danger" : "btn-ghost text-warn-300 border border-warn-700 hover:bg-warn-900/20"}
                disabled={!canSubmit || mutation.isPending}
                onClick={() => mutation.mutate()}
              >
                {mutation.isPending ? "Working…" : m.confirmLabel}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Org tab ────────────────────────────────────────────────────────────────
function OrgTab() {
  const [dangerAction, setDangerAction] = useState<DangerAction>(null);

  const { data: org } = useQuery({
    queryKey: ["org"],
    queryFn: () => api.get<any>("/api/v1/org"),
  });

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-5">
          <div className="text-sm font-medium mb-4">Organization details</div>
          <dl className="space-y-3 text-sm">
            <OrgRow label="Name" value={org?.name} />
            <OrgRow label="Slug" value={org?.slug} mono />
            <OrgRow label="Plan" value={org?.plan ? org.plan.charAt(0).toUpperCase() + org.plan.slice(1) : undefined} />
            <OrgRow label="Region" value={org?.region || "us-east-1"} />
            <OrgRow label="Created" value={org?.created_at
              ? new Date(org.created_at).toLocaleDateString() : undefined} />
          </dl>
        </div>

        <div className="card p-5">
          <div className="text-sm font-medium mb-1">Security defaults</div>
          <p className="text-xs text-ink-500 mb-4">
            These settings reflect Kynara's platform-wide security posture. Per-org overrides are available on Enterprise plans.
          </p>
          <div className="space-y-3 text-sm">
            <ToggleRow label="Fail-closed on policy engine error" checked={true} locked />
            <ToggleRow label="SHA-256 hash-chained audit log" checked={true} locked />
            <ToggleRow label="Require MFA for all non-SSO users" checked={false} comingSoon />
            <ToggleRow label="Auto-lock inactive sessions" checked={false} comingSoon />
          </div>
        </div>

        <div className="card p-5 lg:col-span-2"
          style={{ borderColor: "rgba(244,63,94,0.2)", background: "rgba(244,63,94,0.03)" }}>
          <div className="text-sm font-medium mb-2 text-danger-300">Danger zone</div>
          <p className="text-xs text-ink-400 mb-4">
            These actions are irreversible and will be recorded in the audit log.
          </p>
          <div className="flex gap-3 flex-wrap items-center">
            <button
              className="btn-ghost text-warn-300 flex items-center gap-2"
              onClick={() => setDangerAction("rotate-keys")}
            >
              <RotateCcw className="size-4" /> Rotate all API keys
            </button>
            <button
              className="btn-ghost text-warn-300 flex items-center gap-2"
              onClick={() => setDangerAction("revoke-sessions")}
            >
              <LogOut className="size-4" /> Revoke all active sessions
            </button>
            <button
              className="btn-danger flex items-center gap-2"
              onClick={() => setDangerAction("delete-org")}
            >
              <AlertTriangle className="size-4" /> Delete organization
            </button>
          </div>
        </div>
      </div>

      {dangerAction && (
        <DangerModal
          action={dangerAction}
          orgName={org?.name ?? ""}
          onClose={() => setDangerAction(null)}
        />
      )}
    </>
  );
}

function OrgRow({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex justify-between border-b border-ink-800 pb-3 last:border-0 last:pb-0">
      <dt className="text-ink-400">{label}</dt>
      <dd className={`${mono ? "font-mono text-xs" : ""} text-ink-100`}>{value || "—"}</dd>
    </div>
  );
}

function ToggleRow({ label, checked, locked, comingSoon }: {
  label: string; checked: boolean; locked?: boolean; comingSoon?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-ink-200 text-sm">{label}</span>
      <div className="flex items-center gap-2">
        {comingSoon && (
          <span className="text-[10px] text-ink-600 font-medium uppercase tracking-wide">soon</span>
        )}
        {locked && (
          <span className="text-[10px] text-ink-600 font-medium uppercase tracking-wide">enforced</span>
        )}
        <span className={`relative w-10 h-5 rounded-full transition ${
          checked ? "bg-accent-500" : "bg-ink-700"
        } ${(locked || comingSoon) ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}>
          <span className={`absolute top-0.5 size-4 rounded-full bg-white transition ${
            checked ? "left-5" : "left-0.5"
          }`} />
        </span>
      </div>
    </div>
  );
}

// ── Profile tab ────────────────────────────────────────────────────────────────
function ProfileTab() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="max-w-2xl space-y-8">
      {/* Appearance */}
      <section>
        <h2 className="text-sm font-semibold text-ink-100 mb-1">Appearance</h2>
        <p className="text-xs text-ink-300 mb-5">
          Choose a colour scheme for the Kynara interface. Your preference is saved locally to this browser.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {THEMES.map(t => {
            const active = theme === t.id;
            const isLight = t.id === "mercury-light";
            const cardBorder = isLight ? "1px solid #E3E9F1" : "1px solid rgba(255,255,255,0.08)";
            const labelColor = isLight ? "#0F172A" : "#E8EDF5";
            const swatchBorder = isLight ? "1px solid #DADCE0" : "1px solid rgba(255,255,255,0.15)";
            const shadow = active
              ? `0 0 0 3px ${t.accent}33, 0 4px 20px ${isLight ? "rgba(0,0,0,0.12)" : "rgba(0,0,0,0.4)"}`
              : isLight ? "0 1px 4px rgba(60,64,67,0.12)" : "0 2px 8px rgba(0,0,0,0.3)";
            return (
              <button
                key={t.id}
                onClick={() => setTheme(t.id as ThemeId)}
                className="rounded-xl p-4 text-left transition-all duration-150 relative"
                style={{
                  background: t.sidebar,
                  border: active
                    ? `2px solid ${t.accent}`
                    : isLight ? "2px solid #DADCE0" : "2px solid rgba(148,163,184,0.12)",
                  boxShadow: shadow,
                }}
              >
                {/* Active check */}
                {active && (
                  <span
                    className="absolute top-2.5 right-2.5 size-5 rounded-full flex items-center justify-center"
                    style={{ background: t.accent }}
                  >
                    <Check className="size-3 text-ink-50" strokeWidth={3} />
                  </span>
                )}

                {/* Mini UI preview */}
                <div className="mb-3 rounded-lg overflow-hidden"
                  style={{ border: cardBorder, height: 56 }}>
                  <div className="flex h-full">
                    <div className="w-5 h-full" style={{ background: t.sidebar, borderRight: cardBorder }} />
                    <div className="flex-1 h-full" style={{ background: t.card }}>
                      <div className="p-1.5 space-y-1">
                        {[1, 0.5, 0.3].map((o, i) => (
                          <div key={i} className="h-1.5 rounded-full"
                            style={{ background: t.accent, opacity: o, width: `${60 - i * 15}%` }} />
                        ))}
                      </div>
                      <div className="px-1.5">
                        <div className="h-2.5 rounded"
                          style={{ background: t.accent, width: "50%", opacity: 0.9 }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Labels */}
                <div className="font-semibold text-sm" style={{ color: labelColor }}>{t.label}</div>
                <div className="text-[11px] mt-0.5" style={{ color: t.accent, opacity: isLight ? 1 : 0.85 }}>
                  {t.description}
                </div>

                {/* Colour swatches */}
                <div className="flex items-center gap-1.5 mt-3">
                  <span className="size-3 rounded-full" style={{ background: t.sidebar, border: swatchBorder }} />
                  <span className="size-3 rounded-full" style={{ background: t.card, border: swatchBorder }} />
                  <span className="size-3 rounded-full" style={{ background: t.accent }} />
                </div>
              </button>
            );
          })}
        </div>

        <p className="text-[11px] text-ink-400 mt-4 flex items-center gap-1.5">
          <Palette className="size-3 shrink-0" />
          You can also switch themes instantly using the coloured dots next to your name in the sidebar.
        </p>
      </section>
    </div>
  );
}
 