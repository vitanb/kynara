import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Mail } from "lucide-react";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/api/v1/auth/forgot-password", { email });
      setSent(true);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? "";
      if (!msg || msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        setError("Could not reach the server. Check your connection or try again in a moment.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

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
          {sent ? (
            /* ── Success state ── */
            <div className="text-center py-4">
              <div
                className="size-14 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)" }}
              >
                <Mail className="size-7" style={{ color: "var(--s0-accent-text)" }} />
              </div>
              <h2 className="text-xl font-bold text-ink-50 mb-2">Check your email</h2>
              <p className="text-sm text-ink-300 mb-1">
                We sent a password reset link to
              </p>
              <p className="text-sm font-semibold text-ink-50 mb-5">{email}</p>
              <p className="text-xs text-ink-400 mb-6">
                The link expires in 1 hour. If you don't see the email, check your spam folder.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 text-sm text-ink-300 hover:text-ink-50 transition-colors"
              >
                <ArrowLeft className="size-4" /> Back to sign in
              </Link>
            </div>
          ) : (
            /* ── Form state ── */
            <>
              <div className="mb-6">
                <h2 className="text-xl font-bold text-ink-50">Forgot your password?</h2>
                <p className="text-sm text-ink-300 mt-1">
                  Enter your email and we'll send you a reset link.
                </p>
              </div>

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="label">Work email</label>
                  <input
                    className="input w-full"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                  />
                </div>

                {error && (
                  <div
                    className="rounded-lg px-4 py-3 text-sm text-red-300"
                    style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}
                  >
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full justify-center py-2.5"
                >
                  {loading ? "Sending…" : "Send reset link"}
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
