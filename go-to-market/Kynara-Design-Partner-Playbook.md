# Kynara Design-Partner Playbook

*How to find, pitch, and land your first 8–12 design partners. Focus segments: regulated enterprises and DevOps/SecOps. v1 · June 2026.*

---

## 0. The framing (read this first)

NewCore's "10 design partners" are an **identity** story — CISO/IAM buyers who care about *who the agent is*. Don't copy their target list. Kynara wins on the **authorization and enforcement** layer: *what the agent is allowed to do, in real time, with proof.* So your ideal partner is not "a company that wants agent identity" — it's **a team already running agents that take real, consequential actions** and is now scared of what those agents can do without guardrails.

That buyer is more motivated and more specific than NewCore's, which is your advantage. You don't need 10 logos for vanity — you need **6–10 partners who actually run agents in production**, will give you weekly feedback, and produce a quotable outcome ("Kynara blocked X / gave us the audit trail for our SOC 2"). Quality over count.

**Ideal Design-Partner Profile (ICP)**

| Signal | Strong fit | Weak fit |
|---|---|---|
| Agents do | Real side effects: API calls, refunds, infra changes, sending mail, ticket actions | Read-only chat / RAG Q&A |
| Stage of agents | 1–3 in or near production | Demo / hackathon only |
| Framework | LangChain/LangGraph, CrewAI, AutoGen, MCP servers | Pure prompt-only |
| Who owns risk | A named platform / security / "AI platform" lead | Nobody — it's a side project |
| Pressure | Audit, compliance, an incident, or a nervous CISO | "We'll worry about it later" |
| Speed | Can sign + integrate in <30 days | 6-month procurement for a pilot |

If a prospect fails the **"agents take actions"** and **"someone owns the risk"** tests, deprioritize — they won't feel the pain yet.

---

## 1. Target prospect list

Two priority segments, ranked by how acutely they feel the enforcement pain. Treat named companies as **candidates to research, not vetted facts** — confirm each one is currently shipping action-taking agents before you reach out. Aim to build a working sheet of ~40 names to land ~8–10 partners.

### Segment A — DevOps / SecOps agent teams *(highest urgency, fastest cycles)*

These companies' core product *is* an agent that executes response/remediation actions — quarantine a host, run a playbook, push an infra change, resolve an incident. Per-action authorization, human approval on destructive steps, and a tamper-evident audit log are existential for them. Two ways to win here: (a) they **embed Kynara** as the control layer in their product, or (b) their **internal platform team** uses Kynara to govern the agents they run.

**Agentic SOC / security-automation vendors** (build agents that take response actions):
- **7AI** — agentic security platform, Fortune 2026 Cyber 60. Agents investigate + act.
- **Conifers.ai** — CognitiveSOC platform ($25M raised); autonomous SOC actions.
- **Stellar Cyber** — agentic SOC for lean teams.
- **Dropzone AI**, **Prophet Security**, **Qevlar AI**, **Radiant Security** — autonomous SOC analyst startups (verify current action scope).
- **Torq**, **Tines** — security automation / hyperautomation now adding agentic execution.

**AI SRE / incident-response & DevOps agents** (execute infra + on-call actions):
- **Resolve.ai**, **Cleric**, **Traversal**, **Parity** — AI SRE / root-cause + remediation agents.
- **incident.io**, **PagerDuty**, **Rootly** — incident platforms layering in AI agents.

*Why they convert:* the gap between "agent suggests a fix" and "agent executes the fix" is exactly your allow / deny / require_approval decision + audit. Lead with the **kill-switch + approval + hash-chained log** story.

### Segment B — Regulated enterprises running internal agents *(higher value, slower)*

Fintech, healthcare, insurance — agents doing reconciliation, fraud triage, claims, clinical documentation, customer ops. Explainability and audit are tied directly to compliance, so "prove what the agent did and that it couldn't exceed its mandate" is a board-level concern.

- **Fintech / financial services:** payments, lending, neobanks, and brokerages with internal "AI platform" teams; back-office agents for reconciliation, fraud, and compliance checks. Target the *platform/ML-platform* and *security engineering* teams, not the LOB.
- **Healthcare / health-tech:** companies deploying triage, scheduling, and clinical-documentation agents — HIPAA + audit pull is strong. Your EU AI Act Art. 12 / hash-chained log story lands here.
- **Insurance:** claims and underwriting automation teams.

*Where to find the right ones without a logo list:* don't chase brand-name banks first (procurement death). Target **Series B–D fintech/health-tech** and **innovation/AI-platform teams inside larger regulated firms** — enough usage to feel pain, enough autonomy to sign a design-partner agreement.

### Channels / communities (where these people actually are)

- **MCP ecosystem:** the Model Context Protocol GitHub org/discussions, MCP server authors, and the MCP registry — every server author is a "should this agent be allowed to call this tool?" prospect.
- **Framework communities:** LangChain/LangGraph Discord & forums, CrewAI community, AutoGen GitHub.
- **Security/agent communities:** Latent Space (Discord + events), MLOps Community Slack, the "AI Engineer" community/conference, r/LocalLLaMA and r/AI_Agents for builders, Lobsters/HN for technical credibility.
- **SecOps-specific:** SOC-focused Slacks/Discords, BSides events, and the agentic-SOC vendor communities themselves.
- **Where buyers lurk:** LinkedIn (search below), and design-partner-friendly investor networks (your investors' portfolios are the warmest path of all).

---

## 2. Design-Partner Program — one-pager

*(Send this as the "here's the deal" doc once a prospect is interested. Plain, concrete, time-boxed.)*

### Kynara Design Partner Program

**What it is.** A focused 60–90 day collaboration with a small cohort (max ~10) of teams running AI agents in production. You help us shape the authorization control plane for agents; we give you the product, white-glove support, and commercial perks — free.

**Who it's for.** Teams with at least one agent in or near production that takes real actions (API calls, infra changes, messaging, financial or clinical workflows) and a named owner for agent risk.

**What you (the partner) commit to:**
- A 30-min biweekly feedback call with our team (6–8 sessions).
- Integrate Kynara into at least one real agent workflow (SDK or MCP Gateway) within 30 days.
- Share anonymized usage signals and candid feedback on what's missing.
- If it delivers value: a quote / logo / reference call, and a short case study. (Logo is opt-in, never required to participate.)

**What you get:**
- **Free use** of Kynara through the program and **12 months free** after, at the highest tier you need.
- **Direct line** to the founding team (shared Slack channel) and roadmap influence — your top requests get prioritized.
- **Co-built integration** for your framework/stack, maintained by us.
- **Compliance artifacts** you can show auditors: tamper-evident decision logs, policy export, and an EU AI Act Art. 12 / SOC 2 evidence pack.
- **Locked founder pricing** and design-partner status in any launch materials (opt-in).

**Timeline:**
- Week 0 — 45-min scoping call: pick one agent workflow + 3 policies that matter.
- Week 1 — integrated in a non-prod environment (we pair with you).
- Weeks 2–4 — live on the target workflow; first policies + approvals + audit running.
- Weeks 4–10 — iterate biweekly; expand scope; capture an outcome.
- Week 10–12 — wrap-up, case study (opt-in), convert to paid (free year starts).

**Success criteria (how we'll both know it worked):**
- ≥1 production agent workflow gated by Kynara.
- ≥1 concrete "Kynara caught/prevented/proved X" outcome.
- Audit chain verified and exportable for the partner's compliance use.
- Partner would recommend Kynara to a peer (the real test).

**The ask:** a 45-minute scoping call. No procurement, no cost, no long contract — a design-partner letter, not an MSA.

---

## 3. Outreach kit

Rules: one clear ICP-trigger per message, lead with *their* pain not your features, ask for a small thing (a call), make it obviously low-cost. Never send a feature list cold.

### A. Cold email — SecOps/DevOps agent vendor (embed angle)

> **Subject:** guardrails for {{Company}}'s agents — before they execute
>
> Hi {{First}},
>
> {{Company}}'s agents don't just suggest — they *act* (quarantine, run playbooks, push changes). The hard part isn't the action, it's proving each one was authorized and reversible when a customer's security team asks.
>
> That's what we build at Kynara: a per-action allow / deny / require-approval check for agents, with a non-escalation guarantee and a tamper-evident audit log. Drop-in via SDK or an MCP gateway — no rebuild.
>
> We're taking on a few design partners and I'd love to have {{Company}} as one — free, founder-led, ~30 days to a working integration. Worth a 30-min call to see if it fits?
>
> {{Name}} · {{link to kynaraai.com/security}}

### B. Cold email — regulated enterprise (compliance angle)

> **Subject:** proving what your AI agents did (for audit)
>
> Hi {{First}},
>
> As {{Company}} puts agents into {{reconciliation / triage / claims}}, the question auditors will ask is simple and hard: *what was this agent allowed to do, and can you prove it never exceeded that?*
>
> Kynara is the authorization layer for that — RBAC + ABAC policy decisions on every agent action, human approval on the sensitive ones, and a hash-chained log that maps cleanly to SOC 2 and EU AI Act Article 12 logging.
>
> We're onboarding a small design-partner cohort (free, white-glove, ~30 days to value). Given where {{Company}} is with agents, I think you'd get a lot out of it. Open to a short call?
>
> {{Name}}

### C. LinkedIn DM (short)

> Hi {{First}} — saw {{Company}} is shipping {{agent use case}}. We built the authorization + audit layer for exactly that (allow/deny/approve per action, tamper-evident log). Lining up a few free design partners — would a 20-min chat be worth your time?

### D. Warm-intro request (to an investor / mutual)

> Quick ask: we're picking 8–10 design partners for Kynara (authorization + audit for AI agents that take real actions). Two ideal profiles: (1) SecOps/AI-SRE teams whose agents *execute* changes, (2) regulated teams (fintech/health) running internal agents under audit pressure. Anyone in your network running agents in production who's nervous about control? A one-line intro would mean a lot — happy to send a forwardable blurb.

### E. Forwardable blurb (paste under the warm-intro ask)

> *Kynara is a permission control plane for AI agents — it decides allow / deny / require-approval on every agent action in real time, guarantees an agent can't exceed the human who dispatched it, and keeps a tamper-evident audit log for SOC 2 / EU AI Act. Works with LangChain, CrewAI, AutoGen, and MCP. They're onboarding a few design partners free of charge: {{link}}.*

---

## 4. Sourcing playbook

### Build the pipeline (target: ~40 qualified names → ~8–10 partners)

1. **Warm network first (highest hit rate).** List your investors, advisors, and ex-colleagues. Ask each for intros using template D. Investor portfolios are gold — many have a regulated or infra-tooling company already running agents.
2. **Mine the ecosystems.** MCP registry + GitHub: every published MCP server author is a prospect. LangChain/CrewAI/AutoGen GitHub stargazers and Discord actives who mention "production" or "tools." Note people *asking how to add permissions/guardrails* — they're pre-qualified.
3. **LinkedIn Sales Navigator searches** (title × signal):
   - Titles: "AI Platform", "ML Platform", "Staff/Principal Engineer", "Head of Security Engineering", "SRE Lead", "Platform Eng", "Head of Applied AI".
   - Filter to fintech / health-tech / insurance and to agentic-SOC/SRE vendors.
   - Boolean in posts: `("AI agent" OR "agentic" OR LangChain OR MCP) AND (production OR "in prod" OR guardrails OR permissions)`.
4. **Listen for triggers** (set Google Alerts / LinkedIn saved searches): "deployed agents in production," "agent guardrails," "AI SRE," "agentic SOC," funding announcements for agent startups (fresh raise = budget + urgency to look mature for customers).
5. **Content as a magnet.** You already have the blog cluster + compare pages. Post the "agents that *act* need authorization, not just identity" angle (now extra timely vs. NewCore's launch) on HN, r/AI_Agents, LinkedIn. Add a "Become a design partner" CTA to kynaraai.com. Inbound design partners are the best ones.

### Qualify fast (first call, 4 questions)
1. What does your agent actually *do* — does it take actions with side effects?
2. Is it in production or near it? How many agents?
3. What happens today if it does something it shouldn't? (Listen for fear/gaps.)
4. Who owns that risk internally? (No owner = not ready.)

Green-light if: real actions + near-prod + a named owner + felt pain. Otherwise, nurture, don't onboard.

### Cadence (run this weekly)
- **Mon:** add 10 new qualified names to the sheet; send 5 warm-intro asks.
- **Tue–Thu:** 15–20 cold touches (email + LinkedIn), 2–3 second-touches.
- **Fri:** review replies, book calls, log learnings. Tune messaging on what got replies.
- Expect ~10–20% reply rate on a tight ICP; ~1 in 4 good calls becomes a partner. So ~40 quality conversations → ~8–10 partners.

### Track it (simple sheet columns)
`Company | Segment (SecOps / SRE / Fintech / Health / Insurance) | Agent use case | Takes actions? | Stage | Owner contact | Source (warm/eco/LI/inbound) | Status | Next step | Notes`

### Two things that will 10× your odds
- **Don't sell software — sell the program.** "Be a design partner" is a flattering, low-commitment ask. "Buy our product" is not.
- **Pick partners who'll produce a quote.** One reference-able SecOps or fintech logo with a real outcome is worth more than NewCore's 10.

---

*Next steps you can hand me: (1) build the live tracker as a spreadsheet, (2) add a "Become a design partner" page to kynaraai.com matching your other pages, (3) draft a LinkedIn/HN post on the "identity isn't authorization" angle to capitalize on NewCore's launch news.*
