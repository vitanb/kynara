import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function SignupPage() {
  const navigate = useNavigate();
  const { bootstrap } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", display_name: "", org_name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await api.post<{ access_token: string; refresh_token: string }>(
        "/api/v1/auth/register", form,
      );
      localStorage.setItem("kynara_access", r.access_token);
      localStorage.setItem("kynara_refresh", r.refresh_token);
      await bootstrap();
      navigate("/app/dashboard");
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Registration failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex" style={{ background: "#FFFFFF" }}>
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12"
        style={{ background: "#FAFAF9", borderRight: "1px solid rgba(148,163,184,0.06)" }}>
        <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <img src="/logo.svg" className="w-9 h-9 rounded-lg" alt="Kynara" />
          <span className="font-semibold text-ink-50 text-lg tracking-tight">Kynara</span>
        </Link>

        <div>
          <h2 className="text-3xl font-bold text-ink-50 mb-4">
            Enterprise-grade AI agent control
          </h2>
          <p className="text-ink-400 text-lg leading-relaxed mb-8">
            Govern every tool call, enforce policies in real time, and maintain a tamper-proof audit trail — for every AI agent in your org.
          </p>
          <div className="space-y-3">
            {["Free tier — up to 3 seats", "10,000 policy decisions / month", "Full audit log & role-based access", "Upgrade anytime — no credit card required"].map(f => (
              <div key={f} className="flex items-center gap-3 text-ink-300">
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: "#18181B" }} />
                <span className="text-sm">{f}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-slate-600 text-xs">
          Already have an account?{" "}
          <Link to="/login" className="text-ink-400 hover:text-ink-50 transition-colors">Sign in →</Link>
        </p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <Link to="/" className="flex items-center gap-3 mb-8 lg:hidden hover:opacity-80 transition-opacity">
            <img src="/logo.svg" className="w-9 h-9 rounded-lg" alt="Kynara" />
            <span className="font-semibold text-ink-50 text-lg">Kynara</span>
          </Link>

          <h1 className="text-2xl font-bold text-ink-50 mb-1">Create your account</h1>
          <p className="text-ink-400 mb-8 text-sm">Start with the free plan — no credit card needed</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Your name</label>
              <input className="input w-full" placeholder="Ada Lovelace"
                value={form.display_name} onChange={set("display_name")} required />
            </div>
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Work email</label>
              <input className="input w-full" type="email" placeholder="ada@company.com"
                value={form.email} onChange={set("email")} required />
            </div>
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Password</label>
              <input className="input w-full" type="password" placeholder="Min. 8 characters"
                value={form.password} onChange={set("password")} required minLength={8} />
            </div>
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Organization name</label>
              <input className="input w-full" placeholder="Acme Corp"
                value={form.org_name} onChange={set("org_name")} required />
            </div>

            {error && (
              <div className="rounded-lg px-4 py-3 text-sm text-red-300"
                style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 mt-2">
              {loading ? "Creating account…" : <>Create account <ArrowRight className="w-4 h-4" /></>}
            </button>
          </form>

          <p className="text-ink-400 text-xs text-center mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-ink-300 hover:text-ink-50 transition-colors">Sign in</Link>
          </p>
          <p className="text-slate-600 text-xs text-center mt-2">
            By creating an account you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  );
}
