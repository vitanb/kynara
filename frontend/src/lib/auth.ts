import { create } from "zustand";
import { api } from "./api";

export interface Me {
  user_id: string; email: string; display_name: string | null;
  org_id: string; seat_role: string; scopes: string[]; mfa_enrolled: boolean;
  timezone: string | null; avatar_url: string | null;
  is_superadmin: boolean;
}

export interface OrgSummary {
  org_id: string; org_name: string; slug: string; seat_role: string; plan: string;
}

type State = {
  me: Me | null;
  orgs: OrgSummary[];
  loading: boolean;
  login: (email: string, password: string, orgId?: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
  fetchOrgs: () => Promise<void>;
  switchOrg: (orgId: string) => Promise<void>;
};

export const useAuth = create<State>((set, get) => ({
  me: null,
  orgs: [],
  loading: true,

  bootstrap: async () => {
    const tok = localStorage.getItem("kynara_access");
    if (!tok) { set({ loading: false }); return; }
    try {
      const me = await api.get<Me>("/api/v1/auth/me");
      set({ me, loading: false });
      get().fetchOrgs();
    } catch {
      localStorage.removeItem("kynara_access");
      localStorage.removeItem("kynara_refresh");
      set({ me: null, loading: false });
    }
  },

  login: async (email, password, orgId?) => {
    const r = await api.post<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/login", { email, password, org_id: orgId ?? null },
    );
    localStorage.setItem("kynara_access", r.access_token);
    localStorage.setItem("kynara_refresh", r.refresh_token);
    const me = await api.get<Me>("/api/v1/auth/me");
    set({ me, loading: false });
    get().fetchOrgs();
  },

  logout: async () => {
    try { await api.post("/api/v1/auth/logout"); } catch { /* ignore */ }
    localStorage.removeItem("kynara_access");
    localStorage.removeItem("kynara_refresh");
    set({ me: null, orgs: [] });
    // Also clear the IdP (Auth0) session so the next SSO attempt always
    // prompts for credentials rather than silently reusing the old session.
    window.location.href = "/api/v1/auth/sso/logout?return_to=/login";
  },

  fetchOrgs: async () => {
    try {
      const orgs = await api.get<OrgSummary[]>("/api/v1/auth/me/orgs");
      set({ orgs });
    } catch { /* non-fatal */ }
  },

  switchOrg: async (orgId: string) => {
    // Re-login with the same refresh path — just call refresh with a different org_id
    const r = await api.post<{ access_token: string }>("/api/v1/auth/refresh", {
      refresh_token: localStorage.getItem("kynara_refresh") ?? "",
      org_id: orgId,
    });
    localStorage.setItem("kynara_access", r.access_token);
    const me = await api.get<Me>("/api/v1/auth/me");
    set({ me });
  },
}));
