import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, EyeOff, Eye } from "lucide-react";
import { api } from "@/lib/api";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--s0-card)" }}>
        <div className="card p-8 text-center w-full max-w-md">
          <p className="text-ink-300 mb-4">Invalid or missing reset token.</p>
          <Link to="/forgot-password" className="btn-primary inline-flex">
            Request a new link
          </Link>
        </div>
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/api/v1/auth/reset-password", { token, new_password: password });
      setDone(true);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? "Something went wrong.";
      // Friendly messages for known server errors
      if (msg.includes("expired")) {
        setError("This reset link has expired. Please request a new one.");
      } else if (msg.includes("Invalid") || msg.includes("already-used")) {
        setError("This reset link is invalid or has already been used. Please request a new one.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  const strength = (() => {
    if (password.length === 0) return null;
    if (password.length < 8) return { label: "Too short", color: "#F43F5E", width: "25%" };
    if (password.length < 12) return { label: "Fair", color: "#F59E0B", width: "50%" };
    if (/[A-Z]/.test(password) && /[0-9]/.test(password)) return { label: "Strong", color: "#10B981", width: "100%" };
    return { label: "Good", color: "var(--s0-accent)", width: "75%" };
  })();

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--s0-card)" }}>
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 mb-8 hover:opacity-80 transition-opacity">
          <img
            src="/logo.svg"
            className="size-9 rounded-xl"
            alt="Kynara"
          />
          <div>
            <div className="text-base font-bold text-ink-50 tracking-tight leading-none">Kynara</div>
            <div className="text-[10px] font-medium mt-0.5" style={{ color: "var(--s0-accent-text)", letterSpacing: "0.06em" }}>
              AI Control Plane
            </div>
          </div>
        </Link>

        <div className="card p-8">
          {done ? (
            /* ── Success state ── */
            <div className="text-center py-4">
              <div
                className="size-14 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)" }}
              >
                <CheckCircle2 className="size-7 text-ok-400" />
              </div>
              <h2 className="text-xl font-bold text-ink-50 mb-2">Password updated</h2>
              <p className="text-sm text-ink-300 mb-6">
                Your password has been changed. All other sessions have been signed out for security.
              </p>
              <button
                className="btn-primary w-full justify-center"
                onClick={() => navigate("/login")}
              >
                Sign in with new password
              </button>
            </div>
          ) : (
            /* ── Form state ── */
            <>
              <div className="mb-6">
                <h2 className="text-xl font-bold text-ink-50">Set a new password</h2>
                <p className="text-sm text-ink-300 mt-1">
                  Choose a strong password for your Kynara account.
                </p>
              </div>

              <form onSubmit={submit} className="space-y-4">
                {/* New password */}
                <div>
                  <label className="label">New password</label>
                  <div className="relative">
                    <input
                      className="input w-full pr-10"
                      type={showPwd ? "text" : "password"}
                      placeholder="Min. 8 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      autoFocus
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-200 transition-colors"
                      onClick={() => setShowPwd((v) => !v)}
                      tabIndex={-1}
                    >
                      {showPwd ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                  {/* Strength bar */}
                  {strength && (
                    <div className="mt-2">
                      <div className="h-1 rounded-full overflow-hidden" style={{ background: "rgba(148,163,184,0.1)" }}>
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{ width: strength.width, background: strength.color }}
                        />
                      </div>
                      <div className="text-[11px] mt-1" style={{ color: strength.color }}>
                        {strength.label}
                      </div>
                    </div>
                  )}
                </div>

                {/* Confirm password */}
                <div>
                  <label className="label">Confirm password</label>
                  <div className="relative">
                    <input
                      className="input w-full pr-10"
                      type={showConfirm ? "text" : "password"}
                      placeholder="Repeat your password"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-200 transition-colors"
                      onClick={() => setShowConfirm((v) => !v)}
                      tabIndex={-1}
                    >
                      {showConfirm ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                  {confirm && password !== confirm && (
                    <p className="text-[11px] text-danger-400 mt-1">Passwords don't match</p>
                  )}
                </div>

                {error && (
                  <div
                    className="rounded-lg px-4 py-3 text-sm text-red-300"
                    style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}
                  >
                    {error}{" "}
                    {(error.includes("expired") || error.includes("invalid")) && (
                      <Link to="/forgot-password" className="underline text-red-200 hover:text-ink-50">
                        Request a new link
                      </Link>
                    )}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || password !== confirm || password.length < 8}
                  className="btn-primary w-full justify-center py-2.5 mt-1"
                >
                  {loading ? "Updating…" : "Update password"}
                </button>
              </form>

              <div className="mt-5 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-sm text-ink-400 hover:text-ink-100 transition-colors"
                >
                  <ArrowLeft className="size-4" /> Back to sign in
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
