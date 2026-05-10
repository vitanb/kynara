import { useState } from "react";
import { Link } from "react-router-dom";
import { Hexagon, ArrowLeft, Mail } from "lucide-react";
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
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "#05080F" }}>
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 mb-8 hover:opacity-80 transition-opacity">
          <div
            className="size-9 rounded-xl flex items-center justify-center"
            style={{ background: "#4F46E5", boxShadow: "0 0 0 1px rgba(99,102,241,0.5), 0 4px 14px rgba(79,70,229,0.4)" }}
          >
            <Hexagon className="size-5 text-white" strokeWidth={2} />
          </div>
          <div>
            <div className="text-base font-bold text-white tracking-tight leading-none">Kynara</div>
            <div className="text-[10px] font-medium mt-0.5" style={{ color: "#818CF8", letterSpacing: "0.06em" }}>
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
                style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)" }}
              >
                <Mail className="size-7" style={{ color: "#818CF8" }} />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Check your email</h2>
              <p className="text-sm text-ink-300 mb-1">
                We sent a password reset link to
              </p>
              <p className="text-sm font-semibold text-white mb-5">{email}</p>
              <p className="text-xs text-ink-400 mb-6">
                The link expires in 1 hour. If you don't see the email, check your spam folder.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 text-sm text-ink-300 hover:text-white transition-colors"
              >
                <ArrowLeft className="size-4" /> Back to sign in
              </Link>
            </div>
          ) : (
            /* ── Form state ── */
            <>
              <div className="mb-6">
                <h2 className="text-xl font-bold text-white">Forgot your password?</h2>
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
