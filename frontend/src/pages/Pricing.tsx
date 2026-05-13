import { Link } from "react-router-dom";
import { Check, Zap, Shield, Building2 } from "lucide-react";

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "For individuals and small teams getting started with AI agent governance.",
    icon: Zap,
    iconColor: "#10B981",
    iconBg: "rgba(16,185,129,0.12)",
    cta: "Start for free",
    ctaTo: "/signup",
    highlighted: false,
    features: [
      "Up to 3 seats",
      "10,000 policy decisions / month",
      "2 AI agents",
      "Full audit log (30 day retention)",
      "Role-based access control",
      "Community support",
    ],
    limits: ["No SSO / SAML", "No custom roles", "No SLA"],
  },
  {
    name: "Pro",
    price: "$49",
    period: "per seat / month",
    description: "For growing teams that need more agents, longer audit history, and SSO.",
    icon: Shield,
    iconColor: "#6366F1",
    iconBg: "rgba(99,102,241,0.15)",
    cta: "Start free trial",
    ctaTo: "/signup",
    highlighted: true,
    features: [
      "Unlimited seats",
      "1M policy decisions / month",
      "Unlimited AI agents",
      "Audit log (1 year retention)",
      "SSO / OIDC (Okta, Google, Azure AD)",
      "Custom roles & fine-grained scopes",
      "Webhook alerts",
      "Email support with 24h SLA",
    ],
    limits: [],
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "annual contract",
    description: "For large orgs needing unlimited scale, SAML, on-prem, and dedicated support.",
    icon: Building2,
    iconColor: "#F59E0B",
    iconBg: "rgba(245,158,11,0.12)",
    cta: "Contact sales",
    ctaTo: "mailto:sales@kynara.dev",
    highlighted: false,
    features: [
      "Everything in Pro",
      "Unlimited policy decisions",
      "SAML 2.0 & SCIM provisioning",
      "Audit log (unlimited retention)",
      "On-prem / private cloud deploy",
      "Custom data residency",
      "Dedicated Slack channel",
      "99.99% uptime SLA",
    ],
    limits: [],
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen" style={{ background: "#05080F", color: "#CBD5E1" }}>
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 max-w-6xl mx-auto">
        <Link to="/" className="flex items-center gap-3">
          <img src="/logo.svg" className="w-8 h-8 rounded-lg" alt="Kynara" />
          <span className="font-semibold text-white">Kynara</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/login" className="text-sm text-slate-400 hover:text-white transition-colors">Sign in</Link>
          <Link to="/signup" className="btn-primary text-sm px-4 py-2">Get started</Link>
        </div>
      </nav>

      {/* Hero */}
      <div className="text-center py-16 px-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs mb-6"
          style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", color: "#A5B4FC" }}>
          Simple, transparent pricing
        </div>
        <h1 className="text-4xl lg:text-5xl font-bold text-white mb-4 tracking-tight">
          Govern AI agents at any scale
        </h1>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto">
          Start free. Upgrade when your team grows. No hidden fees, no per-agent pricing traps.
        </p>
      </div>

      {/* Plans */}
      <div className="max-w-6xl mx-auto px-6 pb-24 grid lg:grid-cols-3 gap-6">
        {plans.map((plan) => {
          const Icon = plan.icon;
          return (
            <div
              key={plan.name}
              className="rounded-2xl p-8 flex flex-col"
              style={{
                background: plan.highlighted ? "rgba(99,102,241,0.08)" : "#080C14",
                border: plan.highlighted
                  ? "1px solid rgba(99,102,241,0.35)"
                  : "1px solid rgba(148,163,184,0.08)",
                position: "relative",
              }}
            >
              {plan.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="px-3 py-1 rounded-full text-xs font-medium text-white"
                    style={{ background: "#4F46E5" }}>
                    Most popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                  style={{ background: plan.iconBg }}>
                  <Icon className="w-5 h-5" style={{ color: plan.iconColor }} />
                </div>
                <h2 className="text-xl font-bold text-white mb-1">{plan.name}</h2>
                <p className="text-slate-400 text-sm">{plan.description}</p>
              </div>

              <div className="mb-8">
                <span className="text-4xl font-bold text-white">{plan.price}</span>
                <span className="text-slate-500 text-sm ml-2">{plan.period}</span>
              </div>

              {plan.ctaTo.startsWith("mailto") ? (
                <a href={plan.ctaTo}
                  className="block text-center py-2.5 px-4 rounded-lg font-medium text-sm mb-8 transition-colors"
                  style={{ background: "rgba(148,163,184,0.08)", border: "1px solid rgba(148,163,184,0.15)", color: "#CBD5E1" }}>
                  {plan.cta}
                </a>
              ) : (
                <Link to={plan.ctaTo}
                  className={`block text-center py-2.5 px-4 rounded-lg font-medium text-sm mb-8 transition-colors ${plan.highlighted ? "btn-primary" : ""}`}
                  style={plan.highlighted ? {} : { background: "rgba(148,163,184,0.08)", border: "1px solid rgba(148,163,184,0.15)", color: "#CBD5E1" }}>
                  {plan.cta}
                </Link>
              )}

              <div className="space-y-3 flex-1">
                {plan.features.map(f => (
                  <div key={f} className="flex items-start gap-3">
                    <Check className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "#10B981" }} />
                    <span className="text-sm text-slate-300">{f}</span>
                  </div>
                ))}
                {plan.limits.map(l => (
                  <div key={l} className="flex items-start gap-3 opacity-40">
                    <span className="w-4 h-4 mt-0.5 shrink-0 text-center text-xs leading-4">✕</span>
                    <span className="text-sm text-slate-400">{l}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* FAQ strip */}
      <div className="border-t max-w-6xl mx-auto px-6 py-16" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
        <h2 className="text-xl font-bold text-white mb-8">Common questions</h2>
        <div className="grid md:grid-cols-2 gap-8">
          {[
            ["What counts as a policy decision?", "Any time Kynara evaluates a tool call against your policies — allow, deny, or require approval. Cached evaluations count once."],
            ["Can I change plans later?", "Yes. Upgrade or downgrade at any time. Upgrades take effect immediately; downgrades at the end of your billing period."],
            ["Is there a free trial for Pro?", "Yes — 14 days, no credit card required. You'll be moved to Free automatically if you don't add a card."],
            ["What happens if I exceed my decision quota?", "On Free you'll get a warning at 80% and the system will start denying new decisions at 100%. On Pro, overages are billed at $0.05 per 1,000 decisions."],
          ].map(([q, a]) => (
            <div key={q}>
              <p className="text-white font-medium mb-2 text-sm">{q}</p>
              <p className="text-slate-400 text-sm leading-relaxed">{a}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
