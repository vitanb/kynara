import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import {
  ShieldCheck, GitBranch, Eye, Zap, ArrowRight, Check, X, Send,
  Lock, AlertTriangle, LineChart, ChevronRight, Building2,
} from "lucide-react";

const features = [
  { icon: ShieldCheck, color: "var(--s0-accent-text)", bg: "var(--s0-accent-subtle)", title: "Real-time policy enforcement", desc: "Every tool call, every API action — evaluated against your policy tree in under 5 ms before the agent executes. Allow, deny, or escalate to a human reviewer." },
  { icon: GitBranch, color: "#34D399", bg: "rgba(16,185,129,0.1)", title: "Fine-grained RBAC", desc: "Grant agents the minimum privilege they need. Permissions scoped by org, role, environment, and time window — with JIT grants for elevated access." },
  { icon: Eye, color: "#FBBF24", bg: "rgba(245,158,11,0.1)", title: "Immutable audit trail", desc: "Cryptographically chained log of every decision, actor, context, and outcome. Replay events, investigate incidents, prove compliance to auditors." },
  { icon: Zap, color: "#F472B6", bg: "rgba(236,72,153,0.1)", title: "Guardrails & anomaly detection", desc: "Set spend limits, rate caps, and behavioral thresholds. Kynara auto-revokes agents that exceed them and fires webhook alerts to your SIEM." },
  { icon: Lock, color: "#3F3F46", bg: "rgba(59,130,246,0.1)", title: "SSO & enterprise identity", desc: "SAML 2.0 and OIDC out of the box. Plug into Okta, Azure AD, or any IdP. Role mappings flow automatically from your directory." },
  { icon: LineChart, color: "var(--s0-text-muted)", bg: "var(--s0-accent-subtle)", title: "Live observability", desc: "Decision dashboards, risk scores, and cost attribution per agent. Know exactly which agent is doing what — and flag the risky ones before they cause damage." },
];

const trustSignals = [
  "Sub-5ms decision latency", "Cryptographic audit chain", "SAML 2.0 & OIDC SSO",
  "Role-based access control", "JIT elevated grants", "Webhook & SIEM integration",
  "Anomaly detection & auto-revoke", "SOC 2-ready audit exports",
];

const stats = [
  { value: "<5ms", label: "Median policy decision" },
  { value: "99.99%", label: "Uptime SLA" },
  { value: "10M+", label: "Decisions / month capacity" },
];

export default function LandingPage() {
  const [contactOpen, setContactOpen] = useState(false);
  const [solutionsOpen, setSolutionsOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "" });
  const [contactState, setContactState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  function openContact() {
    setContactOpen(true);
    setContactState("idle");
    setForm({ name: "", email: "", company: "", message: "" });
  }

  async function submitContact(e: React.FormEvent) {
    e.preventDefault();
    setContactState("sending");
    try {
      await api.post("/api/v1/contact", {
        name: form.name.trim(),
        email: form.email.trim(),
        message: `Company: ${form.company.trim()}\n\n${form.message.trim()}`,
      });
      setContactState("sent");
    } catch {
      setContactState("error");
    }
  }

  return (
    <div className="min-h-screen overflow-x-hidden" style={{ background: "var(--s0-card)", color: "#CBD5E1" }}>

      {/* Ambient glow removed for the light monochrome look */}

      <div style={{ position: "relative", zIndex: 1 }}>

        {/* Nav */}
        <nav className="flex items-center justify-between px-8 py-5 max-w-6xl mx-auto">
          <div className="flex items-center gap-3">
            <img src="/logo.svg" className="w-8 h-8 rounded-lg" alt="Kynara" />
            <span className="font-bold text-ink-50 text-base tracking-tight">Kynara</span>
          </div>
          <div className="hidden md:flex items-center gap-7 text-sm text-ink-300">
            <a href="#features" className="hover:text-ink-50 transition-colors">Features</a>
            <a href="/design-partners" className="hover:text-ink-50 transition-colors">Design partners</a>
            {/* Solutions dropdown */}
            <div className="relative" onMouseEnter={() => setSolutionsOpen(true)} onMouseLeave={() => setSolutionsOpen(false)}>
              <button className="flex items-center gap-1 hover:text-ink-50 transition-colors">
                Solutions <ChevronRight className="w-3.5 h-3.5 rotate-90 transition-transform" style={{ transform: solutionsOpen ? "rotate(270deg)" : "rotate(90deg)" }} />
              </button>
              {solutionsOpen && (
                <div className="absolute top-full left-1/2 -translate-x-1/2 pt-3 z-50">
                  <div className="rounded-xl p-3 w-72" style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,0.12)", boxShadow: "0 16px 48px rgba(0,0,0,0.5)" }}>
                    <div className="text-xs font-semibold uppercase tracking-widest text-ink-400 px-2 pb-2 mb-1">By Industry</div>
                    {[
                      { href: "/solutions/financial-services.html", icon: "🏦", label: "Financial Services", desc: "SOC 2, HIPAA, regulated agents" },
                      { href: "/solutions/healthcare.html", icon: "🏥", label: "Healthcare", desc: "HIPAA BAA, patient data, clinical AI" },
                      { href: "/solutions/manufacturing.html", icon: "🏭", label: "Manufacturing", desc: "Industrial IoT, production agents" },
                      { href: "/solutions/devops-engineering.html", icon: "⚙️", label: "DevOps & Engineering", desc: "CI/CD agents, infra automation" },
                      { href: "/solutions/security-operations.html", icon: "🛡️", label: "Security Operations", desc: "SecOps, threat response agents" },
                    ].map((item) => (
                      <a key={item.href} href={item.href}
                        className="flex items-start gap-3 px-2 py-2.5 rounded-lg hover:bg-ink-700 transition-colors group"
                        style={{ textDecoration: "none" }}>
                        <span className="text-lg flex-shrink-0 mt-0.5">{item.icon}</span>
                        <div>
                          <div className="text-sm font-medium text-ink-50 group-hover:text-ink-200 transition-colors">{item.label}</div>
                          <div className="text-xs text-ink-400 mt-0.5">{item.desc}</div>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <a href="/quickstart" className="hover:text-ink-50 transition-colors">Quickstart</a>
            <Link to="/docs" className="hover:text-ink-50 transition-colors">Docs</Link>
            <a href="/security" className="hover:text-ink-50 transition-colors">Security</a>
            <a href="/compare/" className="hover:text-ink-50 transition-colors">Compare</a>
            <a href="/blog/" className="hover:text-ink-50 transition-colors">Blog</a>
            <button onClick={openContact} className="hover:text-ink-50 transition-colors">Contact</button>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-ink-300 hover:text-ink-50 transition-colors hidden sm:block">Sign in</Link>
            <button onClick={openContact} className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-50 px-4 py-2 rounded-lg transition-all hover:opacity-90" style={{ background: "var(--s0-accent)", boxShadow: "0 1px 2px rgba(2,6,23,0.3)" }}>
              Book a demo
            </button>
          </div>
        </nav>

        {/* Hero */}
        <section className="text-center pt-20 pb-20 px-6 max-w-5xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs mb-8" style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)", color: "var(--s0-text-muted)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-ink-400 animate-pulse" />
            AI agent governance infrastructure
          </div>

          <h1 className="text-5xl lg:text-7xl font-bold text-ink-50 mb-6 tracking-tight leading-[1.08]">
            The enterprise permission
            <br />
            <span style={{ color: "var(--s0-accent-text)" }}>
              layer for AI agents
            </span>
          </h1>

          <p className="text-ink-300 text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
            Kynara is the control plane that lets enterprises define, enforce, and audit exactly
            what AI agents can do — in real time, before they act.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <button onClick={openContact} className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-ink-50 transition-all hover:opacity-90" style={{ background: "var(--s0-accent)", boxShadow: "0 1px 2px rgba(2,6,23,0.3)" }}>
              Book a demo <ArrowRight className="w-4 h-4" />
            </button>
            <Link to="/signup" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-medium text-ink-300 hover:text-ink-50 transition-all" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}>
              Start free <ChevronRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-px rounded-2xl overflow-hidden max-w-2xl mx-auto" style={{ background: "rgba(148,163,184,0.08)", border: "1px solid rgba(148,163,184,0.08)" }}>
            {stats.map((s, i) => (
              <div key={i} className="py-6 px-4 text-center" style={{ background: "var(--s0-card)" }}>
                <div className="text-3xl font-bold text-ink-50 mb-1">{s.value}</div>
                <div className="text-xs text-ink-400">{s.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Problem */}
        <section className="max-w-6xl mx-auto px-6 pb-24">
          <div className="rounded-3xl p-px" style={{ background: "linear-gradient(135deg, var(--s0-accent-ring), var(--s0-accent-subtle), var(--s0-accent-subtle))" }}>
            <div className="rounded-[22px] p-12 lg:p-16" style={{ background: "var(--s0-card)" }}>
              <div className="grid lg:grid-cols-2 gap-12 items-center">
                <div>
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-6" style={{ background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.15)", color: "#FCD34D" }}>
                    <AlertTriangle className="w-3 h-3" /> The problem
                  </div>
                  <h2 className="text-3xl lg:text-4xl font-bold text-ink-50 mb-5 leading-tight">
                    AI agents are operating without guardrails
                  </h2>
                  <p className="text-ink-300 leading-relaxed mb-5">
                    Enterprises are deploying AI agents that call APIs, read databases, send emails,
                    and execute code — but have no centralized system to control what they're allowed to do.
                  </p>
                  <p className="text-ink-300 leading-relaxed">
                    When an agent exceeds its scope or gets compromised, companies lack the visibility
                    to detect it and the infrastructure to stop it. That's a compliance failure waiting to happen.
                  </p>
                </div>
                <div className="space-y-3">
                  {[
                    { color: "#F87171", label: "No audit trail", desc: "Can't prove what agents did during an incident or compliance review" },
                    { color: "#FBBF24", label: "Overprivileged agents", desc: "Agents granted broad access 'just in case' — violating least-privilege" },
                    { color: "#F472B6", label: "Zero runtime enforcement", desc: "Permissions set once at deploy time, never checked per-action" },
                    { color: "#3F3F46", label: "Compliance blind spots", desc: "No SOC 2, ISO 27001, or GDPR controls for AI agent activity" },
                  ].map((item) => (
                    <div key={item.label} className="flex gap-4 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(148,163,184,0.06)" }}>
                      <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: item.color }} />
                      <div>
                        <div className="text-sm font-semibold text-ink-50 mb-0.5">{item.label}</div>
                        <div className="text-xs text-ink-400 leading-relaxed">{item.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Terminal mockup */}
        <section className="max-w-5xl mx-auto px-6 pb-24">
          <div className="rounded-2xl overflow-hidden" style={{ border: "1px solid rgba(148,163,184,0.08)", boxShadow: "0 8px 24px rgba(2,6,23,0.4)" }}>
            <div className="flex items-center gap-2 px-4 py-3" style={{ background: "#0D1117", borderBottom: "1px solid rgba(148,163,184,0.06)" }}>
              <div className="w-3 h-3 rounded-full" style={{ background: "#FF5F57" }} />
              <div className="w-3 h-3 rounded-full" style={{ background: "#FEBC2E" }} />
              <div className="w-3 h-3 rounded-full" style={{ background: "#28C840" }} />
              <span className="ml-3 text-xs text-ink-400 font-mono">kynara · policy decision engine</span>
            </div>
            <div className="p-7 font-mono text-sm" style={{ background: "var(--s0-card-elevated)" }}>
              <div className="space-y-3 text-ink-400">
                <div><span className="text-ink-400">POST </span><span style={{ color: "var(--s0-accent-text)" }}>/api/v1/decisions/check</span></div>
                <div className="pl-4 space-y-1">
                  <div><span style={{ color: "#3F3F46" }}>"agent_id"</span>{': '}<span style={{ color: "#34D399" }}>"agent_billing_processor"</span></div>
                  <div><span style={{ color: "#3F3F46" }}>"tool"</span>{': '}<span style={{ color: "#34D399" }}>"stripe.charge_customer"</span></div>
                  <div><span style={{ color: "#3F3F46" }}>"context"</span>{': { '}<span style={{ color: "#3F3F46" }}>"amount_usd"</span>{': '}<span style={{ color: "#FBBF24" }}>4200</span>{' }'}</div>
                </div>
                <div className="border-t pt-3" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full" style={{ background: "#F87171" }} />
                    <span className="text-ink-50 font-semibold">DENY</span>
                    <span className="text-slate-700">·</span>
                    <span>policy: <span style={{ color: "#FBBF24" }}>max_charge_usd = 1000</span></span>
                    <span className="text-slate-700">·</span>
                    <span>3.2 ms</span>
                  </div>
                </div>
                <div className="pl-4 space-y-1">
                  <div><span style={{ color: "#3F3F46" }}>"decision"</span>{': '}<span style={{ color: "#F87171" }}>"deny"</span></div>
                  <div><span style={{ color: "#3F3F46" }}>"reason"</span>{': '}<span style={{ color: "#34D399" }}>"charge_amount exceeds policy limit"</span></div>
                  <div><span style={{ color: "#3F3F46" }}>"escalate_to"</span>{': '}<span style={{ color: "#34D399" }}>"finance-approvals@company.com"</span></div>
                  <div><span style={{ color: "#3F3F46" }}>"audit_id"</span>{': '}<span style={{ color: "var(--s0-text-muted)" }}>"evt_01HXYZ..."</span></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="max-w-6xl mx-auto px-6 pb-24">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-5" style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)", color: "var(--s0-text-muted)" }}>
              Full-stack governance
            </div>
            <h2 className="text-3xl lg:text-4xl font-bold text-ink-50 mb-4">Everything security teams need</h2>
            <p className="text-ink-300 max-w-lg mx-auto text-sm leading-relaxed">
              From developer-facing API keys to org-wide audit exports — Kynara covers the full lifecycle of AI agent authorization and compliance.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {features.map((f) => {
              const Icon = f.icon;
              return (
                <div key={f.title} className="rounded-2xl p-6" style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,0.07)" }}>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{ background: f.bg }}>
                    <Icon className="w-5 h-5" style={{ color: f.color }} />
                  </div>
                  <h3 className="text-ink-50 font-semibold mb-2 text-sm">{f.title}</h3>
                  <p className="text-ink-400 text-sm leading-relaxed">{f.desc}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Trust signals */}
        <section className="max-w-6xl mx-auto px-6 pb-24">
          <div className="rounded-2xl p-10" style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,0.07)" }}>
            <div className="flex items-center gap-3 mb-8">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: "var(--s0-accent-subtle)" }}>
                <Building2 className="w-4 h-4" style={{ color: "var(--s0-accent-text)" }} />
              </div>
              <div>
                <div className="text-ink-50 font-semibold text-sm">Built for enterprise compliance</div>
                <div className="text-ink-400 text-xs mt-0.5">Controls aligned with SOC 2, ISO 27001, and NIST AI RMF</div>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {trustSignals.map((signal) => (
                <div key={signal} className="flex items-center gap-2">
                  <Check className="w-4 h-4 flex-shrink-0" style={{ color: "#34D399" }} />
                  <span className="text-ink-300 text-xs">{signal}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Social proof */}
        <section className="max-w-5xl mx-auto px-6 pb-20">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-4" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)", color: "#34D399" }}>
              Early access
            </div>
            <h2 className="text-2xl lg:text-3xl font-bold text-ink-50">Trusted by teams building with AI agents</h2>
          </div>

          {/* Quotes */}
          <div className="grid md:grid-cols-2 gap-6 mb-14">
            {[
              {
                quote: "Kynara gave our security team the visibility they needed before we'd go live with agents in production. The audit chain alone solved our SOC 2 gap.",
                name: "Head of Platform Security",
                company: "Series B FinTech",
                initial: "S",
                color: "var(--s0-accent-text)",
              },
              {
                quote: "We evaluated OPA and Casbin. Kynara was the only option that had the human approval flow built in — not as an afterthought. That's what our compliance team actually wanted.",
                name: "Staff Engineer",
                company: "Enterprise SaaS",
                initial: "E",
                color: "#34D399",
              },
            ].map((t, i) => (
              <div key={i} className="rounded-2xl p-7" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(148,163,184,0.08)" }}>
                <div className="text-2xl mb-4" style={{ color: "rgba(148,163,184,0.2)", fontFamily: "Georgia, serif" }}>"</div>
                <p className="text-ink-300 leading-relaxed mb-6 text-sm">{t.quote}</p>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-ink-50" style={{ background: `linear-gradient(135deg, ${t.color}40, ${t.color}20)`, border: `1px solid ${t.color}40` }}>{t.initial}</div>
                  <div>
                    <div className="text-sm font-semibold text-ink-50">{t.name}</div>
                    <div className="text-xs text-ink-400">{t.company}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Ask AI section */}
          <div className="rounded-2xl p-8 text-center" style={{ background: "rgba(255,255,255,0.015)", border: "1px solid rgba(148,163,184,0.07)" }}>
            <div className="text-sm font-semibold text-ink-300 mb-2">Still researching?</div>
            <div className="text-ink-50 font-bold text-lg mb-1">Ask your AI assistant about Kynara</div>
            <div className="text-ink-400 text-sm mb-6">Get a plain-English explanation from the AI you already use.</div>
            <div className="flex flex-wrap items-center justify-center gap-3">
              {[
                {
                  label: "Ask ChatGPT",
                  href: "https://chatgpt.com/?q=Explain+what+Kynara+(kynaraai.com)+does+and+how+it+helps+enterprises+govern+AI+agents.+Use+https://kynaraai.com+as+the+source.",
                  bg: "rgba(16,163,127,0.1)", border: "rgba(16,163,127,0.25)", color: "#34D399",
                  icon: "✦"
                },
                {
                  label: "Ask Claude",
                  href: "https://claude.ai/new?q=Explain+what+Kynara+(kynaraai.com)+does+and+how+it+helps+enterprises+govern+AI+agents.+Use+https://kynaraai.com+as+the+source.",
                  bg: "rgba(210,145,77,0.1)", border: "rgba(210,145,77,0.25)", color: "#F0A050",
                  icon: "◆"
                },
                {
                  label: "Ask Perplexity",
                  href: "https://www.perplexity.ai/?q=Explain+what+Kynara+(kynaraai.com)+does+and+how+it+helps+enterprises+govern+AI+agents.+Use+https://kynaraai.com+as+the+source.",
                  bg: "var(--s0-accent-subtle)", border: "var(--s0-accent-ring)", color: "var(--s0-accent-text)",
                  icon: "⬡"
                },
              ].map((ai) => (
                <a key={ai.label} href={ai.href} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-80"
                  style={{ background: ai.bg, border: `1px solid ${ai.border}`, color: ai.color }}>
                  <span>{ai.icon}</span> {ai.label}
                </a>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="max-w-4xl mx-auto px-6 pb-28">
          <div className="rounded-3xl p-px" style={{ background: "linear-gradient(135deg, var(--s0-accent-ring), var(--s0-accent-subtle), var(--s0-accent-ring))" }}>
            <div className="rounded-[22px] py-16 px-12 text-center" style={{ background: "var(--s0-card-elevated)" }}>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-6" style={{ background: "var(--s0-accent-subtle)", border: "1px solid var(--s0-accent-ring)", color: "var(--s0-text-muted)" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-ink-400 animate-pulse" />
                Accepting design partners
              </div>
              <h2 className="text-3xl lg:text-4xl font-bold text-ink-50 mb-4 leading-tight">
                Ready to govern your AI agents?
              </h2>
              <p className="text-ink-300 mb-8 max-w-md mx-auto leading-relaxed">
                We're working with a select group of enterprises to shape the product.
                Book a 30-minute call to see Kynara in action.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
                <button onClick={openContact} className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-semibold text-ink-50 hover:opacity-90 transition-all" style={{ background: "var(--s0-accent)", boxShadow: "0 1px 2px rgba(2,6,23,0.3)" }}>
                  Book a demo <ArrowRight className="w-4 h-4" />
                </button>
                <Link to="/signup" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl text-sm font-medium text-ink-300 hover:text-ink-50 transition-all" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}>
                  Start free
                </Link>
              </div>
              <div className="flex items-center justify-center gap-6 text-xs text-ink-400">
                {["Free to start", "No credit card", "Dedicated onboarding"].map((t) => (
                  <span key={t} className="flex items-center gap-1.5">
                    <Check className="w-3.5 h-3.5 text-emerald-500" /> {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t px-8 py-8 max-w-6xl mx-auto" style={{ borderColor: "rgba(148,163,184,0.07)" }}>
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-ink-400">
            <div className="flex items-center gap-2.5">
              <img src="/logo.svg" className="w-6 h-6 rounded-md" alt="Kynara" />
              <span className="text-ink-400 font-medium">Kynara</span>
              <span className="text-slate-700">·</span>
              <span>© {new Date().getFullYear()}. All rights reserved.</span>
            </div>
            <div className="flex items-center gap-6">
              <a href="#features" className="hover:text-ink-300 transition-colors">Features</a>
              <a href="/design-partners" className="hover:text-ink-300 transition-colors">Design partners</a>
              <Link to="/docs" className="hover:text-ink-300 transition-colors">Docs</Link>
              <a href="/security" className="hover:text-ink-300 transition-colors">Security</a>
              <a href="/sandbox.html" className="hover:text-ink-300 transition-colors">Policy Sandbox</a>
              <a href="/solutions/financial-services.html" className="hover:text-ink-300 transition-colors">FinServ</a>
              <Link to="/login" className="hover:text-ink-300 transition-colors">Sign in</Link>
              <button onClick={openContact} className="hover:text-ink-300 transition-colors">Contact</button>
            </div>
          </div>
        </footer>

      </div>

      {/* Contact / Demo modal */}
      {contactOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setContactOpen(false); }}>
          <div className="w-full max-w-md rounded-2xl p-7 relative" style={{ background: "var(--s0-card-elevated)", border: "1px solid rgba(148,163,184,0.1)", boxShadow: "0 16px 48px rgba(2,6,23,0.5)" }}>
            <button onClick={() => setContactOpen(false)} className="absolute top-4 right-4 text-ink-400 hover:text-ink-300 transition-colors">
              <X className="w-4 h-4" />
            </button>
            {contactState === "sent" ? (
              <div className="text-center py-8">
                <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-5" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
                  <Check className="w-6 h-6" style={{ color: "#34D399" }} />
                </div>
                <div className="text-xl font-bold text-ink-50 mb-2">We'll be in touch</div>
                <p className="text-sm text-ink-300 mb-6">Expect a reply within one business day.</p>
                <button onClick={() => setContactOpen(false)} className="text-sm font-medium px-5 py-2.5 rounded-lg text-ink-50" style={{ background: "var(--s0-accent)" }}>Close</button>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <div className="flex items-center gap-2.5 mb-3">
                    <img src="/logo.svg" className="w-7 h-7 rounded-lg" alt="Kynara" />
                    <span className="font-bold text-ink-50 text-sm">Kynara</span>
                  </div>
                  <h2 className="text-xl font-bold text-ink-50 mb-1">Book a demo</h2>
                  <p className="text-sm text-ink-300">We'll walk you through the product and discuss your use case.</p>
                </div>
                <form onSubmit={submitContact} className="space-y-4">
                  {[
                    { label: "Full name", key: "name", placeholder: "Jane Smith", type: "text" },
                    { label: "Work email", key: "email", placeholder: "jane@company.com", type: "email" },
                    { label: "Company", key: "company", placeholder: "Acme Corp", type: "text" },
                  ].map(({ label, key, placeholder, type }) => (
                    <div key={key}>
                      <label className="block text-xs font-medium text-ink-300 mb-1.5">{label}</label>
                      <input required type={type} value={form[key as keyof typeof form]}
                        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                        placeholder={placeholder}
                        className="w-full rounded-lg px-3 py-2.5 text-sm text-ink-100 placeholder:text-ink-400 outline-none"
                        style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}
                      />
                    </div>
                  ))}
                  <div>
                    <label className="block text-xs font-medium text-ink-300 mb-1.5">What are you trying to solve? <span className="text-ink-400">(optional)</span></label>
                    <textarea rows={3} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
                      placeholder="e.g. We need to audit what our AI assistants are doing in production…"
                      className="w-full rounded-lg px-3 py-2.5 text-sm text-ink-100 placeholder:text-ink-400 outline-none resize-none"
                      style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}
                    />
                  </div>
                  {contactState === "error" && <p className="text-xs text-red-400">Something went wrong. Please try again.</p>}
                  <button type="submit" disabled={contactState === "sending"}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold text-ink-50 transition-opacity disabled:opacity-60"
                    style={{ background: "var(--s0-accent)", boxShadow: "0 1px 2px rgba(2,6,23,0.3)" }}>
                    <Send className="w-3.5 h-3.5" />
                    {contactState === "sending" ? "Sending…" : "Request demo"}
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
