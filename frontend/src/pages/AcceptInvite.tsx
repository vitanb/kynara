import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface InviteInfo {
  invite_id: string;
  org_name: string;
  seat_role: string;
  email: string | null;
  valid: boolean;
}

export default function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { bootstrap } = useAuth();

  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  useEffect(() => {
    if (!token) { setNotFound(true); return; }
    api.get<InviteInfo>(`/api/v1/invites/${token}`)
      .then(d => {
        setInfo(d);
        if (d.email) setForm(f => ({ ...f, email: d.email ?? "" }));
      })
      .catch(() => setNotFound(true));
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await api.post<{ access_token: string; refresh_token: string }>(
        "/api/v1/invites/accept",
        { token, ...form },
      );
      localStorage.setItem("kynara_access", r.access_token);
      localStorage.setItem("kynara_refresh", r.refresh_token);
      await bootstrap();
      navigate("/app/dashboard");
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Failed to accept invite");
    } finally {
      setLoading(false);
    }
  }

  if (notFound) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#FFFFFF" }}>
        <div className="text-center">
          <p className="text-ink-400 mb-4">This invite link is invalid or has expired.</p>
          <a href="/signup" className="btn-primary px-6 py-2">Create a new account</a>
        </div>
      </div>
    );
  }

  if (!info) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#FFFFFF" }}>
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!info.valid) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#FFFFFF" }}>
        <div className="text-center">
          <p className="text-ink-400 mb-4">This invite has already been used or revoked.</p>
          <a href="/login" className="btn-primary px-6 py-2">Sign in</a>
        </div>
      </div>
    );
  }

  const roleLabel: Record<string, string> = {
    owner: "Owner", admin: "Admin", developer: "Developer",
    auditor: "Auditor", member: "Member",
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "#FFFFFF" }}>
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center gap-3 mb-8 hover:opacity-80 transition-opacity">
          <img src="/logo.svg" className="w-9 h-9 rounded-lg" alt="Kynara" />
          <span className="font-semibold text-ink-50 text-lg">Kynara</span>
        </Link>

        <div className="card p-8">
          <div className="mb-6">
            <p className="text-ink-400 text-sm mb-1">You've been invited to join</p>
            <h1 className="text-2xl font-bold text-ink-50">{info.org_name}</h1>
            <div className="mt-2">
              <span className="pill-info text-xs">{roleLabel[info.seat_role] ?? info.seat_role}</span>
            </div>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Your name</label>
              <input className="input w-full" placeholder="Ada Lovelace"
                value={form.display_name} onChange={set("display_name")} required />
            </div>
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Email</label>
              <input className="input w-full" type="email"
                value={form.email} onChange={set("email")}
                readOnly={!!info.email} required
                style={info.email ? { opacity: 0.6, cursor: "not-allowed" } : {}} />
            </div>
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Password</label>
              <input className="input w-full" type="password" placeholder="Min. 8 characters"
                value={form.password} onChange={set("password")} required minLength={8} />
            </div>

            {error && (
              <div className="rounded-lg px-4 py-3 text-sm text-red-300"
                style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 mt-2">
              {loading ? "Joining…" : <>Accept invite <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>

          <p className="text-ink-400 text-xs text-center mt-4">
            Already have an account?{" "}
            <a href="/login" className="text-ink-300 hover:text-ink-50 transition-colors">Sign in instead</a>
          </p>
        </div>
      </div>
    </div>
  );
}
