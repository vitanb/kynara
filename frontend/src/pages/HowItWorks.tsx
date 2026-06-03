import { useNavigate } from "react-router-dom";
import {
  Bot, Wrench, KeyRound, ShieldCheck, CheckCircle2,
  ArrowRight, Lock,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";

function Step({ n, icon: Icon, title, color, description }: {
  n: number; icon: any; title: string; color: string; description: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center shrink-0">
        <div
          className="size-10 rounded-full flex items-center justify-center border text-sm font-bold"
          style={{ background: `${color}15`, borderColor: `${color}35`, color }}
        >
          {n}
        </div>
        <div className="w-px flex-1 mt-2" style={{ background: "var(--s0-border)" }} />
      </div>
      <div className="pb-8 flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <Icon className="size-4 shrink-0" style={{ color }} />
          <span className="text-sm font-semibold text-ink-200">{title}</span>
        </div>
        <div className="text-[13px] text-ink-400 leading-relaxed">{description}</div>
      </div>
    </div>
  );
}

export default function HowItWorksPage() {
  const nav = useNavigate();
  const accent = "var(--s0-accent)";
  const accentHex = "#6366f1";

  return (
    <div>
      <PageHeader
        title="How it works"
        subtitle="A plain-English guide to how Kynara controls what your AI agents are allowed to do."
      />

      <div className="px-8 py-6 max-w-3xl space-y-8">

        {/* ── Setup steps ── */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-ink-50 mb-6">Setting up access control</h2>

          <Step n={1} icon={Bot} title="Register an Agent" color={accentHex} description={
            <>
              Go to <strong className="text-ink-300">Agents</strong> and create an agent. Give it a name and slug that identifies it in your system (e.g. <code className="font-mono text-accent-300">crm-assistant</code>). The agent's UUID becomes its permanent identity — every permission lookup uses this ID, not its name.
            </>
          } />

          <Step n={2} icon={Wrench} title="Register actions in the Scope Catalog" color="#8b5cf6" description={
            <>
              Go to <strong className="text-ink-300">Scope Catalog</strong> and register every action the agent might need to perform. Each entry has a dot-separated scope string (e.g. <code className="font-mono text-accent-300">payments.refund.issue</code>), a risk level, and a description. This is your authoritative catalog of what actions exist — nothing outside this catalog can be granted.
            </>
          } />

          <Step n={3} icon={KeyRound} title="Create a Role and assign it" color="#06b6d4" description={
            <>
              Go to <strong className="text-ink-300">Roles</strong> and create a named role (e.g. <em>Payments Agent</em>). Use the scope picker to select the actions from the catalog that this role can perform. Then go back to the Agent → <strong className="text-ink-300">Assignments</strong> and assign this role to the agent. This sets the <em>ceiling</em> of what the agent can ever do — no policy can grant permissions beyond what the role allows.
            </>
          } />

          <Step n={4} icon={ShieldCheck} title="Write a Policy and bind it" color="#10b981" description={
            <>
              Go to <strong className="text-ink-300">Policies</strong> and create a policy. Set its effect (<em>allow</em>, <em>deny</em>, or <em>require approval</em>) and the actions it applies to. Optionally add a condition to restrict it further — e.g. only during business hours or only from certain countries. Then bind the policy to the agent's selector so the engine picks it up at runtime.
            </>
          } />

          <Step n={5} icon={CheckCircle2} title="Approvals (optional)" color="#f59e0b" description={
            <>
              If a policy has effect <em>require_approval</em>, any matching request is held in the <strong className="text-ink-300">Approvals</strong> queue instead of being allowed immediately. A reviewer accepts or rejects it — only then does the agent get the go-ahead. Use this for high-risk actions where a human checkpoint is needed before execution.
            </>
          } />

          {/* Last step — no connector line */}
          <div className="flex gap-4">
            <div className="flex flex-col items-center shrink-0">
              <div className="size-10 rounded-full flex items-center justify-center border text-sm font-bold"
                style={{ background: "#f8717115", borderColor: "#f8717135", color: "#f87171" }}>
                ✓
              </div>
            </div>
            <div className="flex-1 min-w-0 pt-2">
              <span className="text-sm font-semibold text-ink-200">Agent is ready</span>
              <p className="text-[13px] text-ink-400 mt-1 leading-relaxed">
                Use the built-in simulator inside any policy to verify requests resolve as expected before going live.
              </p>
            </div>
          </div>
        </div>

        {/* ── Runtime pipeline ── */}
        <div className="card p-6">
          <h2 className="text-sm font-semibold text-ink-50 mb-1">What happens at runtime</h2>
          <p className="text-[13px] text-ink-500 mb-5">Every time an agent tries to perform an action, the engine runs this pipeline in order:</p>

          <div className="space-y-3">
            {[
              {
                label: "Gate 1 · RBAC",
                color: "#6366f1",
                body: "Does the agent's Role grant a scope that covers the requested action? If not, the request is denied immediately. Policies never run. This is the ceiling check.",
                outcome: "deny if no matching scope",
              },
              {
                label: "Gate 2 · ABAC",
                color: "#10b981",
                body: "Walk all policies bound to this agent, in ascending priority order. The first policy whose action pattern, resource type, and condition all match wins. Its effect is applied.",
                outcome: "allow · deny · require_approval",
              },
              {
                label: "Approvals",
                color: "#f59e0b",
                body: "If the winning policy's effect is require_approval, a pending approval record is created and the action is blocked until a reviewer acts on it.",
                outcome: "held until human approves",
              },
              {
                label: "Default",
                color: "#f87171",
                body: "If no policy matched, the engine applies the organisation's default effect — deny. Kynara is fail-closed: silence means no.",
                outcome: "deny",
              },
            ].map(({ label, color, body, outcome }) => (
              <div key={label} className="flex gap-3 rounded-lg border border-ink-800 p-4"
                style={{ background: `${color}08` }}>
                <div className="shrink-0 mt-0.5">
                  <Lock className="size-4" style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-semibold" style={{ color }}>{label}</span>
                    <span className="font-mono text-[10px] text-ink-500">{outcome}</span>
                  </div>
                  <p className="text-[12px] text-ink-400 leading-relaxed">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Quick links ── */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-ink-50 mb-3">Jump to a section</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {[
              { label: "Agents",           path: "/app/agents" },
              { label: "Scope Catalog",    path: "/app/tools" },
              { label: "Roles",            path: "/app/roles" },
              { label: "Policies",         path: "/app/policies" },
              { label: "Approvals",        path: "/app/approvals" },
            ].map(({ label, path }) => (
              <button
                key={path}
                onClick={() => nav(path)}
                className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-ink-800 hover:border-accent-500/40 hover:bg-accent-500/5 transition-colors text-left"
              >
                <ArrowRight className="size-3.5 text-accent-400 shrink-0" />
                <span className="text-xs text-ink-300">{label}</span>
              </button>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
