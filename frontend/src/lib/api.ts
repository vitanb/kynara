const BASE = import.meta.env.VITE_API_BASE || "";

type JsonInit = Omit<RequestInit, "body"> & { json?: unknown };

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API ${status}: ${JSON.stringify(body).slice(0, 200)}`);
  }
}

function getToken() { return localStorage.getItem("kynara_access"); }
function getRefresh() { return localStorage.getItem("kynara_refresh"); }

function authHeader(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

let _refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const rt = getRefresh();
  if (!rt) return false;
  try {
    const res = await fetch(BASE + "/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
      credentials: "include",
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("kynara_access", data.access_token);
    if (data.refresh_token) localStorage.setItem("kynara_refresh", data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(path: string, init: JsonInit = {}, retry = true): Promise<T> {
  const token = getToken();
  const res = await fetch(BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(init.headers || {}),
    },
    body: init.json !== undefined ? JSON.stringify(init.json) : (init as RequestInit).body,
    // Only send credentials on authenticated requests — unauthenticated cross-origin
    // requests with credentials: "include" require an exact CORS origin match and
    // can silently fail with "Failed to fetch" if the backend origin list is off.
    credentials: token ? "include" : "same-origin",
  });

  // On 401, try to refresh the token once and retry
  if (res.status === 401 && retry) {
    if (!_refreshing) _refreshing = tryRefresh().finally(() => { _refreshing = null; });
    const ok = await _refreshing;
    if (ok) return request<T>(path, init, false);
    // Refresh failed — clear session and redirect to login
    localStorage.removeItem("kynara_access");
    localStorage.removeItem("kynara_refresh");
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }

  const txt = await res.text();
  const data = txt ? JSON.parse(txt) : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export const api = {
  get:   <T>(p: string) => request<T>(p),
  post:  <T>(p: string, json?: unknown) => request<T>(p, { method: "POST", json }),
  put:   <T>(p: string, json?: unknown) => request<T>(p, { method: "PUT", json }),
  patch: <T>(p: string, json?: unknown) => request<T>(p, { method: "PATCH", json }),
  del:   <T>(p: string) => request<T>(p, { method: "DELETE" }),
};
