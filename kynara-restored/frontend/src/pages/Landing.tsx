import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import {
  Hexagon,
  ShieldCheck,
  GitBranch,
  Eye,
  Zap,
  ArrowRight,
  Check,
  X,
  Send,
} from "lucide-react";

const features = [
  {
    icon: ShieldCheck,
    color: "#6366F1",
    bg: "rgba(99,102,241,0.12)",
    title: "Policy-first access control",
    desc: "Define exactly what each AI agent can and cannot do — per tool, per org, per role. Decisions are enforced in real time, not reviewed after the fact.",
  },
  {
    icon: GitBranch,
    color: "#10B981",
    bg: "rgba(16,185,129,0.12)",
    title: "Fine-grained permissions",
    desc: "Grant agents the minimum privilege they need. Kynara evaluates every tool call against your policy tree and returns allow, deny, or require-approval.",
  },
  {
    icon: Eye,
    color: "#F59E0B",
    bg: "rgba(245,158,11,0.12)",
    title: "Full audit trail",
    desc: "Every decision is logged with actor, context, and outcome. Replay events, investigate incidents, and stay compliant — all from one place.",
  },
  {
    icon: Zap,
    color: "#EC4899",
    bg: "rgba(236,72,153,0.12)",
    title: "Zero-latency decisions",
    desc: "Sub-5ms cached policy evaluation so your agents never slow down waiting for permission checks.",
  },
];

const stats = [
  { value: "<5ms", label: "Median decision latency" },
  { value: "99.99%", label: "Uptime SLA (Enterprise)" },
  { value: "10k+", label: "Policy decisions / month free" },
];

export default function LandingPage() {
  const [contactOpen, setContactOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [contactState, setContactState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function submitContact(e: React.FormEvent) {
    e.preventDefault();
    setContactState("sending");
    try {
      await api.post("/api/v1/contact", {
        name: form.name.trim(),
        email: form.email.trim(),
        message: form.message.trim(),
      });
      setContactState("sent");
    } catch (err) {
      console.error("Contact form failed:", err);
      setContactState("error");
    }
  }

  return (
    <div className="min-h-screen" style={{ background: "#05080F", color: "#CBD5E1" }}>
      {/* ── Nav ── */}
      <nav className="flex items-center justify-between px-8 py-5 max-w-6xl mx-auto">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "#4F46E5", boxShadow: "0 0 16px rgba(99,102,241,0.4)" }}
          >
            <Hexagon className="w-4 h-4 text-white" strokeWidth={2} />
          </div>
          <span className="font-semibold text-white text-base tracking-tight">Kynara</span>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-slate-400">
          <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
          <Link to="/docs" className="hover:text-white transition-colors">Docs</Link>
          <button onClick={() => { setContactOpen(true); setContactState("idle"); setForm({ name: "", email: "", message: "" }); }}
            className="hover:text-white transition-colors">Contact</button>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/login" className="text-sm text-slate-400 hover:text-white transition-colors">
            Sign in
          </Link>
          <Link
            to="/signup"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-white px-4 py-2 rounded-lg transition-all"
            style={{ background: "#4F46E5", boxShadow: "0 0 0 1px rgba(99,102,241,0.5)" }}
          >
            Get started free
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="text-center pt-20 pb-24 px-6">
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-6"
          style={{
            background: "rgba(99,102,241,0.1)",
            border: "1px solid rgba(99,102,241,0.25)",
            color: "#A5B4FC",
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
          Now in early access — free to start
        </div>

        <h1
          className="text-5xl lg:text-6xl font-bold text-white mb-6 tracking-tight leading-tight max-w-3xl mx-auto"
        >
          The permission layer for{" "}
          <span style={{ color: "#818CF8" }}>AI agents</span>
        </h1>

        <p className="text-slate-400 text-lg max-w-xl mx-auto mb-10 leading-relaxed">
          Kynara is an open control plane that lets your team define, enforce, and audit
          exactly what AI agents can do — before they do it.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            to="/signup"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold text-white transition-all"
            style={{
              background: "#4F46E5",
              boxShadow: "0 0 0 1px rgba(99,102,241,0.5), 0 4px 20px rgba(79,70,229,0.35)",
            }}
          >
            Start for free <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/pricing"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-slate-300 hover:text-white transition-colors"
            style={{
              background: "rgba(148,163,184,0.06)",
              border: "1px solid rgba(148,163,184,0.12)",
            }}
          >
            View pricing
          </Link>
        </div>
      </section>

      {/* ── Stats bar ── */}
      <div
        className="max-w-4xl mx-auto px-6 py-10 mb-16 rounded-2xl grid grid-cols-3 gap-8 text-center"
        style={{
          background: "rgba(13,20,33,0.8)",
          border: "1px solid rgba(148,163,184,0.08)",
        }}
      >
        {stats.map((s) => (
          <div key={s.label}>
            <div className="text-3xl font-bold text-white mb-1">{s.value}</div>
            <div className="text-xs text-slate-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* ── Features ── */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold text-white mb-3">
            Everything you need to govern AI agents
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto text-sm">
            From developer-facing API keys to org-wide audit logs — Kynara covers the full
            lifecycle of AI agent authorization.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="rounded-2xl p-7"
                style={{
                  background: "#080C14",
                  border: "1px solid rgba(148,163,184,0.08)",
                }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                  style={{ background: f.bg }}
                >
                  <Icon className="w-5 h-5" style={{ color: f.color }} />
                </div>
                <h3 className="text-white font-semibold mb-2">{f.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── CTA banner ── */}
      <section className="max-w-4xl mx-auto px-6 pb-28">
        <div
          className="rounded-2xl p-12 text-center"
          style={{
            background:
              "radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.18) 0%, rgba(13,20,33,0.9) 70%)",
            border: "1px solid rgba(99,102,241,0.2)",
          }}
        >
          <h2 className="text-3xl font-bold text-white mb-3">
            Ready to take control of your agents?
          </h2>
          <p className="text-slate-400 mb-8 max-w-md mx-auto text-sm">
            Get started in minutes. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-8">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold text-white"
              style={{ background: "#4F46E5", boxShadow: "0 4px 20px rgba(79,70,229,0.4)" }}
            >
              Create free account <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="flex items-center justify-center gap-6 text-xs text-slate-500">
            {["Free forever plan", "3 seats included", "No credit card"].map((t) => (
              <span key={t} className="flex items-center gap-1.5">
                <Check className="w-3.5 h-3.5 text-emerald-500" /> {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer
        className="border-t px-8 py-8 max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-600"
        style={{ borderColor: "rgba(148,163,184,0.08)" }}
      >
        <div className="flex items-center gap-2">
          <Hexagon className="w-3.5 h-3.5" style={{ color: "#4F46E5" }} />
          <span>© {new Date().getFullYear()} Kynara. All rights reserved.</span>
        </div>
        <div className="flex items-center gap-5">
          <Link to="/pricing" className="hover:text-slate-400 transition-colors">Pricing</Link>
          <Link to="/docs" className="hover:text-slate-400 transition-colors">Docs</Link>
          <Link to="/login" className="hover:text-slate-400 transition-colors">Sign in</Link>
          <button onClick={() => { setContactOpen(true); setContactState("idle"); setForm({ name: "", email: "", message: "" }); }}
            className="hover:text-slate-400 transition-colors">Contact</button>
        </div>
      </footer>

      {/* ── Contact modal ── */}
      {contactOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setContactOpen(false); }}>
          <div className="w-full max-w-md rounded-2xl p-7 relative"
            style={{ background: "#080C14", border: "1px solid rgba(148,163,184,0.12)" }}>
            <button onClick={() => setContactOpen(false)}
              className="absolute top-4 right-4 text-slate-500 hover:text-slate-300 transition-colors">
              <X className="w-4 h-4" />
            </button>

            {contactState === "sent" ? (
              <div className="text-center py-6">
                <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
                  style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(4,120,87,0.3)" }}>
                  <Check className="w-5 h-5" style={{ color: "#34D399" }} />
                </div>
                <div className="text-lg font-bold text-white mb-2">Message sent!</div>
                <p className="text-sm text-slate-400">We'll get back to you shortly.</p>
                <button onClick={() => setContactOpen(false)}
                  className="mt-5 text-sm font-medium px-4 py-2 rounded-lg text-white"
                  style={{ background: "#4F46E5" }}>Close</button>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <h2 className="text-xl font-bold text-white mb-1">Get in touch</h2>
                  <p className="text-sm text-slate-400">We'll reply within one business day.</p>
                </div>
                <form onSubmit={submitContact} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">Name</label>
                    <input
                      required
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Your name"
                      className="w-full rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 outline-none"
                      style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.12)" }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">Email</label>
                    <input
                      required
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="you@company.com"
                      className="w-full rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 outline-none"
                      style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.12)" }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">Message</label>
                    <textarea
                      required
                      rows={4}
                      value={form.message}
                      onChange={(e) => setForm({ ...form, message: e.target.value })}
                      placeholder="How can we help?"
                      className="w-full rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 outline-none resize-none"
                      style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.12)" }}
                    />
                  </div>
                  {contactState === "error" && (
                    <p className="text-xs text-red-400">Something went wrong. Please try again.</p>
                  )}
                  <button type="submit" disabled={contactState === "sending"}
                    className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-60"
                    style={{ background: "#4F46E5" }}>
                    <Send className="w-3.5 h-3.5" />
                    {contactState === "sending" ? "Sending…" : "Send message"}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
