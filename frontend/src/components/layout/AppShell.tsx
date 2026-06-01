import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate, useLocation, Link } from "react-router-dom";
import {
  LayoutDashboard, Bot, Wrench, ShieldCheck, ScrollText,
  CreditCard, Settings, LogOut, ChevronDown, Check, Building2,
  Menu, X, CheckCircle2, Plug, ShieldAlert, KeyRound, BookOpen, UserCircle, Crown, Blocks,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTheme, THEMES, type ThemeId } from "@/lib/theme";

type NavItem = { to: string; label: string; icon: React.ElementType; roles: string[]; badge?: boolean; superadminOnly?: boolean };
type NavGroup = { group: string; icon: React.ElementType; roles: string[]; items: NavItem[] };
type NavEntry = NavItem | NavGroup;

const allNav: NavEntry[] = [
  { to: "dashboard",  label: "Dashboard",  icon: LayoutDashboard, roles: ["owner","admin","developer","auditor","member"] },
  { to: "agents",     label: "Agents",     icon: Bot,             roles: ["owner","admin","developer","auditor","member"] },
  { to: "policies",   label: "Policies",   icon: ShieldCheck,     roles: ["owner","admin","auditor","developer","member"] },
  { to: "approvals",  label: "Approvals",  icon: CheckCircle2,    roles: ["owner","admin","auditor","developer","member"], badge: true },
  { to: "audit",      label: "Audit log",  icon: ScrollText,      roles: ["owner","admin","auditor","developer","member"] },
  {
    group: "Governance",
    icon: KeyRound,
    roles: ["owner","admin","auditor","developer","member"],
    items: [
      { to: "roles",      label: "Roles",         icon: KeyRound,   roles: ["owner","admin","auditor","developer","member"] },
      { to: "tools",      label: "Scope Catalog", icon: Wrench,     roles: ["owner","admin","developer","auditor","member"] },
      { to: "guardrails", label: "Guardrails",    icon: ShieldAlert,roles: ["owner","admin"] },
      { to: "catalog",    label: "Library",       icon: BookOpen,   roles: ["owner","admin","developer","auditor","member"] },
      { to: "how-it-works", label: "How it works",icon: BookOpen,   roles: ["owner","admin","developer","auditor","member"] },
    ],
  },
  {
    group: "Platform",
    icon: Plug,
    roles: ["owner","admin"],
    items: [
      { to: "webhooks",     label: "Webhooks",     icon: Plug,      roles: ["owner","admin"] },
      { to: "integrations", label: "Integrations", icon: Blocks,    roles: ["owner","admin"] },
      { to: "billing",      label: "Billing",      icon: CreditCard,roles: ["owner","admin"] },
      { to: "settings",     label: "Settings",     icon: Settings,  roles: ["owner","admin"] },
    ],
  },
  { to: "superadmin", label: "Super Admin", icon: Crown, roles: ["owner","admin","developer","auditor","member"], superadminOnly: true },
];

function isGroup(entry: NavEntry): entry is NavGroup { return "group" in entry; }


// ── NavItems component ────────────────────────────────────────────────────────

function NavItems({ nav, pendingApprovals, location, role }: {
  nav: NavEntry[];
  pendingApprovals: number;
  location: ReturnType<typeof import("react-router-dom").useLocation>;
  role: string;
}) {
  const activePath = location.pathname.split("/").pop() || "";
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    // Auto-expand the group containing the current route
    const init: Record<string, boolean> = {};
    for (const entry of nav) {
      if (isGroup(entry)) {
        const hasActive = entry.items.some(i => activePath === i.to || location.pathname.endsWith("/" + i.to));
        init[entry.group] = hasActive;
      }
    }
    return init;
  });

  function toggleGroup(group: string) {
    setOpenGroups(prev => ({ ...prev, [group]: !prev[group] }));
  }

  return (
    <nav className="flex-1 px-2 pt-2 pb-3 overflow-y-auto" style={{ display: "flex", flexDirection: "column", gap: "1px" }}>
      {nav.map((entry) => {
        if (!isGroup(entry)) {
          const Icon = entry.icon;
          return (
            <NavLink
              key={entry.to}
              to={entry.to}
              className={({ isActive }) => isActive ? "nav-item-active" : "nav-item"}
            >
              <Icon className="size-4 shrink-0" />
              <span className="flex-1">{entry.label}</span>
              {entry.badge && pendingApprovals > 0 && (
                <span className="text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1 shrink-0"
                  style={{ background: "#F59E0B", color: "#000" }}>
                  {pendingApprovals > 99 ? "99+" : pendingApprovals}
                </span>
              )}
            </NavLink>
          );
        }

        // Group entry
        const GroupIcon = entry.icon;
        const isOpen = !!openGroups[entry.group];
        const hasActiveChild = entry.items.some(i =>
          activePath === i.to || location.pathname.endsWith("/" + i.to)
        );
        const visibleItems = entry.items.filter(i => i.roles.includes(role));
        if (visibleItems.length === 0) return null;

        return (
          <div key={entry.group}>
            <button
              onClick={() => toggleGroup(entry.group)}
              className="nav-item w-full"
              style={hasActiveChild ? { color: "var(--s0-accent-text)" } : {}}
            >
              <GroupIcon className="size-4 shrink-0" />
              <span className="flex-1 text-left">{entry.group}</span>
              <ChevronDown
                className="size-3 shrink-0 transition-transform"
                style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)", color: "var(--s0-text-muted)" }}
              />
            </button>
            {isOpen && (
              <div className="ml-3 mt-0.5 mb-0.5 border-l pl-2" style={{ borderColor: "rgba(148,163,184,0.1)" }}>
                {visibleItems.map(item => {
                  const ItemIcon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) => isActive ? "nav-item-active" : "nav-item"}
                      style={{ paddingTop: "5px", paddingBottom: "5px" }}
                    >
                      <ItemIcon className="size-3.5 shrink-0" />
                      <span className="flex-1 text-[13px]">{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}

export default function AppShell() {
  const { me, orgs, logout, switchOrg } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, setTheme } = useTheme();
  const initials = (me?.display_name || me?.email || "?")[0].toUpperCase();
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const role = me?.seat_role ?? "member";
  const nav = allNav.filter(entry => {
    if (isGroup(entry)) return entry.roles.includes(role);
    return entry.roles.includes(role) && (!('superadminOnly' in entry && entry.superadminOnly) || Boolean(me?.is_superadmin));
  });
  const currentOrg = orgs.find(o => o.org_id === me?.org_id);

  const { data: approvalCountData } = useQuery<{ pending_count: number }>({
    queryKey: ["approvals-count"],
    queryFn: () => api.get("/api/v1/approvals/pending-count"),
    enabled: ["owner","admin","auditor","developer","member"].includes(role),
    refetchInterval: 30_000,
  });
  const pendingApprovals = approvalCountData?.pending_count ?? 0;

  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);
  useEffect(() => {
    document.body.style.overflow = sidebarOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [sidebarOpen]);

  async function handleSwitchOrg(orgId: string) {
    if (orgId === me?.org_id) { setOrgMenuOpen(false); return; }
    setSwitching(true);
    try {
      await switchOrg(orgId);
      navigate("/app/dashboard");
    } finally {
      setSwitching(false);
      setOrgMenuOpen(false);
    }
  }

  const Sidebar = () => (
    <aside
      className="w-60 shrink-0 flex flex-col h-full"
      style={{ background: "var(--s0-sidebar)", borderRight: "1px solid var(--s0-border)" }}
    >
      {/* Logo */}
      <Link
        to="/"
        className="px-4 py-3 flex items-center gap-3 hover:opacity-80 transition-opacity"
        style={{ borderBottom: "1px solid var(--s0-border)" }}
      >
        <img
          src="/logo.svg"
          className="size-8 rounded-lg shrink-0"
          alt="Kynara"
        />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold tracking-tight text-white leading-none">Kynara</div>
          <div className="text-[10px] font-medium mt-0.5" style={{ color: "var(--s0-accent-text)", letterSpacing: "0.06em" }}>
            AI Control Plane
          </div>
        </div>
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden text-ink-400 hover:text-ink-100 transition-colors ml-1 shrink-0"
          aria-label="Close menu"
        >
          <X className="size-4" />
        </button>
      </Link>

      {/* Org switcher */}
      {orgs.length > 0 && (
        <div className="px-3 pt-2 pb-1 relative">
          <button
            onClick={() => setOrgMenuOpen(o => !o)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors"
            style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.08)" }}
          >
            <Building2 className="size-3.5 shrink-0" style={{ color: "var(--s0-accent-text)" }} />
            <span className="flex-1 text-xs text-slate-200 truncate font-medium">
              {switching ? "Switching…" : (currentOrg?.org_name ?? "Select org")}
            </span>
            <ChevronDown className={`size-3 text-slate-500 transition-transform ${orgMenuOpen ? "rotate-180" : ""}`} />
          </button>
          {orgMenuOpen && (
            <div
              className="absolute left-3 right-3 top-full mt-1 z-50 rounded-xl overflow-hidden shadow-xl"
              style={{ background: "var(--s0-card)", border: "1px solid rgba(148,163,184,0.12)" }}
            >
              {orgs.map(org => (
                <button
                  key={org.org_id}
                  onClick={() => handleSwitchOrg(org.org_id)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-white/5 transition-colors"
                >
                  <div
                    className="size-6 rounded-md flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                    style={{ background: "var(--s0-accent)" }}
                  >
                    {org.org_name[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-slate-200 truncate">{org.org_name}</div>
                    <div className="text-[10px] text-slate-500">{org.seat_role}</div>
                  </div>
                  {org.org_id === me?.org_id && <Check className="size-3 shrink-0" style={{ color: "var(--s0-accent-text)" }} />}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Nav links */}
      <NavItems
        nav={nav}
        pendingApprovals={pendingApprovals}
        location={location}
        role={role}
      />

      {/* User footer */}
      <div className="p-3" style={{ borderTop: "1px solid var(--s0-border)" }}>
        <div className="flex items-center gap-2.5 px-1 py-1 rounded-lg">
          {/* Avatar + name — links to profile */}
          <Link
            to="profile"
            className="flex items-center gap-2 flex-1 min-w-0 rounded-md hover:bg-white/5 transition-colors px-0.5 py-0.5"
            title="My profile"
          >
            {me?.avatar_url ? (
              <img
                src={me.avatar_url}
                alt="avatar"
                className="size-7 rounded-md object-cover shrink-0"
                style={{ border: "1px solid var(--s0-border)" }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            ) : (
              <div
                className="size-7 rounded-md flex items-center justify-center shrink-0 text-[11px] font-bold text-white"
                style={{ background: "var(--s0-accent)" }}
              >
                {initials}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-ink-50 truncate leading-none">
                {me?.display_name || me?.email}
              </div>
              <div className="text-[10px] text-ink-400 truncate mt-0.5 flex items-center gap-0.5">
                <UserCircle className="size-2.5 shrink-0" /> Profile
              </div>
            </div>
          </Link>
          <div className="flex items-center gap-1 shrink-0">
            {/* Mini theme switcher — 3 dots */}
            <div className="flex items-center gap-0.5 mr-0.5">
              {THEMES.map(t => (
                <button
                  key={t.id}
                  onClick={() => setTheme(t.id as ThemeId)}
                  title={t.label}
                  className="size-3.5 rounded-full transition-all duration-150 flex items-center justify-center"
                  style={{
                    background: t.accent,
                    outline: theme === t.id ? `2px solid ${t.accent}` : "2px solid transparent",
                    outlineOffset: "2px",
                    opacity: theme === t.id ? 1 : 0.45,
                  }}
                />
              ))}
            </div>
            <button
              onClick={async () => { await logout(); navigate("/login"); }}
              className="shrink-0 text-ink-400 hover:text-ink-100 transition-colors"
              title="Sign out"
            >
              <LogOut className="size-3.5" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="flex h-full">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex flex-col w-60 shrink-0 h-full">
        <Sidebar />
      </div>

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)" }}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}
      {/* Mobile drawer */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-60 flex flex-col lg:hidden transition-transform duration-300 ease-in-out ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <header
          className="lg:hidden flex items-center gap-3 px-4 py-3 shrink-0"
          style={{
            background: "var(--s0-sidebar)",
            borderBottom: "1px solid var(--s0-border)",
          }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-ink-400 hover:text-ink-100 transition-colors p-1 -ml-1"
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <img
              src="/logo.svg"
              className="size-6 rounded-md"
              alt="Kynara"
            />
            <span className="text-sm font-bold text-white">Kynara</span>
          </Link>
        </header>

        <main className="flex-1 overflow-y-auto" style={{ background: "var(--s0-page)" }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
