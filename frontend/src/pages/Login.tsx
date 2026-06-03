import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { KeyRound, ShieldCheck, Activity, FileText, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

const features = [
  {
    icon: ShieldCheck,
    label: "Policy-as-code enforcement",
    sub: "RBAC + ABAC with fail-closed defaults",
    color: "var(--s0-accent)",
    bg: "var(--s0-accent-subtle)",
    border: "var(--s0-accent-ring)",
  },
  {
    icon: Activity,
    label: "Tamper-evident audit log",
    sub: "SHA-256 hash-chained, append-only Postgres",
    color: "#10B981",
    bg: "rgba(16,185,129,0.1)",
    border: "rgba(16,185,129,0.2)",
  },
  {
    icon: FileText,
    label: "Built-in compliance",
    sub: "SOC 2 · ISO 27001 · HIPAA · GDPR ready",
    color: "#2DD4BF",
    bg: "rgba(45,212,191,0.1)",
    border: "rgba(45,212,191,0.2)",
  },
];

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const ssoErrorParam = searchParams.get("sso_error");
  const [err, setErr] = useState<string | null>(
    ssoErrorParam ? "SSO sign-in failed — please try again or contact your admin." : null
  );
  const [busy, setBusy] = useState(false);

  // SSO email picker state
  const [ssoMode, setSsoMode] = useState(false);
  const [ssoEmail, setSsoEmail] = useState("");
  const [ssoErr, setSsoErr] = useState<string | null>(null);
  const [ssoBusy, setSsoBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await login(email, password);
      // If redirected here from OAuth consent (or any protected page), go back.
      const next = searchParams.get("next");
      nav(next ? decodeURIComponent(next) : "/app/dashboard");
    } catch {
      setErr("Invalid email or password.");
    } finally { setBusy(false); }
  }

  async function startSso(e: React.FormEvent) {
    e.preventDefault();
    setSsoErr(null);
    if (!ssoEmail.includes("@")) { setSsoErr("Enter a valid work email."); return; }
    setSsoBusy(true);
    try {
      // Look up which connection handles this email domain
      const { connections } = await api.get<any>(`/api/v1/auth/sso/lookup?email=${encodeURIComponent(ssoEmail)}`);
      if (!connections?.length) {
        setSsoErr("No SSO provider is configured for that email domain. Contact your admin.");
        return;
      }
      // Start OIDC flow with the first matching connection
      const { redirect_url } = await api.post<any>("/api/v1/auth/sso/oidc/start", {
        connection_id: connections[0].id,
        email: ssoEmail,
      });
      window.location.href = redirect_url;
    } catch {
      setSsoErr("Failed to start SSO. Please try again or contact your admin.");
    } finally {
      setSsoBusy(false);
    }
  }

  return (
    <div className="flex min-h-full" style={{ background: "var(--s0-card)" }}>

      {/* ── Left panel ───────────────────────────────────── */}
      <div
        className="hidden lg:flex flex-col justify-between w-[46%] p-14 relative"
        style={{
          background: "var(--s0-card-elevated)",
          borderRight: "1px solid rgba(148,163,184,0.07)",
        }}
      >
        {/* Very subtle top-left indigo gradient */}
        <div
          className="absolute top-0 left-0 w-96 h-96 pointer-events-none"
          style={{
            background: "radial-gradient(ellipse at 0% 0%, var(--s0-accent-subtle) 0%, transparent 65%)",
          }}
        />

        {/* Logo */}
        <Link to="/" className="relative z-10 flex items-center gap-3 hover:opacity-80 transition-opacity">
          <img src="/logo.svg" className="size-9 rounded-xl" alt="Kynara" />
          <div>
            <div className="text-base font-bold text-ink-50 tracking-tight leading-none">Kynara</div>
            <div className="text-[10px] font-medium mt-0.5" style={{ color: "var(--s0-accent-text)", letterSpacing: "0.06em" }}>
              AI Control Plane
            </div>
          </div>
        </Link>

        {/* Headline */}
        <div className="relative z-10 space-y-8">
          <div className="space-y-4">
            <div
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold"
              style={{
                background: "var(--s0-accent-subtle)",
                border: "1px solid var(--s0-accent-ring)",
                color: "var(--s0-accent-text)",
                letterSpacing: "0.04em",
              }}
            >
              <span
                className="size-1.5 rounded-full"
                style={{ background: "var(--s0-accent)", boxShadow: "0 0 6px #18181B" }}
              />
              Enterprise AI permissions platform
            </div>

            <h1 className="text-3xl font-bold leading-tight text-ink-50">
              Every agent action<br />evaluated in real time.
            </h1>
            <p className="text-sm text-ink-300 leading-relaxed max-w-md">
              Kynara is the permission control plane for AI agents. Define what your
              agents can do, on behalf of whom, and under what conditions — and produce
              an auditable record for every decision.
            </p>
          </div>

          {/* Feature list */}
          <div className="space-y-3">
            {features.map((f) => (
              <div key={f.label} className="flex items-center gap-3">
                <div
                  className="size-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: f.bg, border: `1px solid ${f.border}` }}
                >
                  <f.icon className="size-4" style={{ color: f.color }} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-ink-50">{f.label}</div>
                  <div className="text-xs text-ink-300">{f.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom badges */}
        <div className="relative z-10 flex items-center gap-2 flex-wrap">
          {["SOC 2 Type II", "ISO 27001", "HIPAA BAA", "GDPR DPA"].map((b) => (
            <span
              key={b}
              className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md"
              style={{
                border: "1px solid rgba(148,163,184,0.12)",
                color: "#64748B",
                background: "rgba(148,163,184,0.04)",
              }}
            >
              {b}
            </span>
          ))}
        </div>
      </div>

      {/* ── Right sign-in panel ───────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <Link to="/" className="flex items-center gap-2.5 mb-8 lg:hidden hover:opacity-80 transition-opacity">
            <img
              src="/logo.svg"
              className="size-8 rounded-lg"
              alt="Kynara"
            />
            <span className="text-sm font-bold text-ink-50">Kynara</span>
          </Link>

          <div className="mb-7">
            <h2 className="text-2xl font-bold text-ink-50">Sign in</h2>
            <p className="text-sm text-ink-300 mt-1">to your Kynara workspace</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Work email</label>
              <input
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="label mb-0">Password</label>
                <Link
                  to="/forgot-password"
                  className="text-[11px] text-ink-300 hover:text-ink-50 transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
              />
            </div>

            {err && (
              <div
                className="rounded-lg px-3 py-2.5 text-xs text-danger-400 flex items-center gap-2"
                style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(190,18,60,0.25)" }}
              >
                {err}
              </div>
            )}

            <button
              className="btn-primary w-full justify-center py-2.5 mt-1"
              disabled={busy}
            >
              {busy ? "Signing in…" : (
                <>Sign in <ArrowRight className="size-4" /></>
              )}
            </button>
          </form>

          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full" style={{ borderTop: "1px solid rgba(148,163,184,0.1)" }} />
            </div>
          </div>

          {!ssoMode ? (
            <button
              type="button"
              onClick={() => setSsoMode(true)}
              className="btn-secondary w-full justify-center"
            >
              <KeyRound className="size-4" />
              Sign in via SSO
            </button>
          ) : (
            <form onSubmit={startSso} className="space-y-3">
              <div>
                <label className="label">Work email for SSO</label>
                <input
                  className="input"
                  type="email"
                  autoFocus
                  placeholder="you@company.com"
                  value={ssoEmail}
                  onChange={(e) => setSsoEmail(e.target.value)}
                />
              </div>
              {ssoErr && (
                <div
                  className="rounded-lg px-3 py-2 text-xs text-danger-400"
                  style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(190,18,60,0.25)" }}
                >
                  {ssoErr}
                </div>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-ghost flex-1 justify-center"
                  onClick={() => { setSsoMode(false); setSsoErr(null); }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary flex-1 justify-center"
                  disabled={ssoBusy}
                >
                  <KeyRound className="size-4" />
                  {ssoBusy ? "Looking up…" : "Continue with SSO"}
                </button>
              </div>
            </form>
          )}

          <p className="text-center text-xs text-ink-400 mt-4">
            No account?{" "}
            <Link to="/signup" className="text-ink-300 hover:text-ink-50 transition-colors">Create one free →</Link>
          </p>

        </div>
      </div>
    </div>
  );
}
