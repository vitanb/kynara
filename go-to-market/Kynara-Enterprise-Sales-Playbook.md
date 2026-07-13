# Kynara Enterprise Sales Playbook

*A repeatable, founder-led motion for the first 90 days. Goal: land 8–10 design partners and convert 1–2 into paid pilots — while building the machine that makes the next 10 deals repeatable. v1 · June 2026.*

---

## 0. Operating thesis

You are not "doing sales" — you are **building a repeatable system while closing the first deals with your own hands**. Every artifact you create once (a discovery script, a POC plan, a security packet) becomes a reusable asset. By day 90 you should have both first paid pilots *and* a documented motion you could hand to a first AE.

Three principles run through everything:

1. **Sell the program, not the software.** "Be a design partner" is a flattering, low-commitment ask that converts; "buy our product" from a pre-revenue startup does not. The paid pilot is the *graduation*, not the opening.
2. **Only agents that act.** Your qualified buyer runs agents that take consequential actions (API calls, infra changes, messaging, money movement) and has a named owner for that risk. Everything else is a distraction this quarter.
3. **Written success criteria or it didn't happen.** Enterprise deals die in ambiguity. Every stage has an exit criterion, and every POC has a signed-off definition of success before it starts.

**90-day north-star:** 1–2 signed paid pilots.
**Leading indicators that predict it:** qualified accounts in pipeline (target 40), discovery calls held (12–15), active design partners (8–10), technical validations/POCs running (2–3).

---

## 1. ICP & what a qualified opportunity is

Reuse the sharp profile — don't widen it under pressure.

**Fit signals:** agents take real actions · 1–3 agents in/near production · built on LangChain/LangGraph, CrewAI, AutoGen, or MCP · a named platform/security owner for agent risk · felt pain (audit, an incident, a nervous CISO) · can integrate in ~30 days.

**Priority segments (from your GTM work):** DevOps/SecOps agent teams (agentic SOC, AI SRE) as the fastest converters; regulated enterprises (fintech, health, insurance) as higher-value, slower.

**A qualified opportunity (all four, or it's not real):**

| | Question it answers |
|---|---|
| **Pain** | Something bad happens today if an agent misbehaves — and they know it. |
| **Owner** | A specific person owns agent risk and can pull budget. |
| **Action** | Agents take side-effecting actions, in or near prod. |
| **Path** | There's a realistic route to a decision in this quarter (not 9-month procurement). |

If any is missing: nurture, don't advance. Discipline here is the whole game at 40 accounts.

---

## 2. The repeatable pipeline (stage model)

This is the core of "repeatable." Fixed stages, fixed entry/exit criteria, so every deal moves the same way and your funnel math is trustworthy.

| Stage | Definition | Exit criterion (advance when…) |
|---|---|---|
| **S0 Target** | ICP-fit account identified | Named account + a specific person to reach |
| **S1 Engaged** | First conversation booked | Discovery call on the calendar |
| **S2 Discovery** | Qualifying the four pillars | Pain + owner + action + path confirmed in writing |
| **S3 DP Scoping** | Design-partner fit agreed | One workflow + 3 policies chosen; DP letter sent |
| **S4 Technical Validation** | POC running against real workflow | Written success criteria signed; integrated in non-prod |
| **S5 Paid Pilot** | Commercial pilot agreed | Order form / pilot agreement signed |
| **S6 Expansion** *(post-90)* | Pilot → annual, more agents/teams | Renewal or expansion SOW |

Rule: an opportunity sits in exactly one stage, and you never skip S2 (discovery) or S4's written success criteria — those are where enterprise deals silently rot.

---

## 3. Playbook by stage

### S1→S2 — Engage & discover
**Who:** your champion (the platform/security engineer who feels the pain) — plus, early, an ask to meet the economic buyer.
**Do:** a 30–45 min discovery call. Talk 30%, listen 70%. Diagnose before you demo.
**Discovery question bank (agent-specific MEDDPICC):**

- *Metrics:* How many agents, doing what actions? What's the cost of one bad action — a wrong refund, a leaked record, a bad infra change?
- *Economic buyer:* Who owns agent risk? Whose budget would this come from?
- *Decision process:* What would you need to see to put this in production? Is there a security review? Who signs off?
- *Identify pain:* What happens today if an agent does something it shouldn't? Walk me through the last time you worried about it.
- *Champion:* Who lives with this problem daily? (That's who you arm.)
- *Competition:* Building it yourself? Using OPA/Cerbos? An identity vendor? Doing nothing?
- *Paper process:* Security questionnaire, DPA, procurement — what's the path?

**Exit:** you can write one sentence — "*[Company]* runs *[agents]* that *[action]*; *[owner]* is worried about *[pain]*; the path to prod is *[process]*." If you can't, you haven't qualified.

### S2→S3 — Demo & design-partner scoping
**The 10-minute demo (map every beat to their stated pain):**

1. Real-time **deny** before a risky action runs.
2. **Human approval** on a sensitive action (pause → approve → resume).
3. **Audit chain → Verify Chain** (tamper-evident proof for their auditor).
4. **Argument-level policy** (Slack channel / Gmail recipient) — enforce intent, not just the action.
5. **Dynamic downgrade on untrusted input** (`is_tainted`) — the OWASP/MITRE story; injection can't lift it.
6. **Non-escalation** — an agent can't exceed the human who dispatched it.

Then propose the design-partner program: pick **one workflow + three policies**, send the DP letter (you have it), agree a start date.
**Exit:** DP letter acknowledged; scoping call booked.

### S3→S4 — Technical validation (POC)
This is where enterprises decide. Run it like a project, not a hope.

- **Timebox:** 2–4 weeks. Longer = stalled.
- **Mutual success criteria, signed before you start:** e.g., "Kynara blocks X, routes Y to approval, and produces an exportable audit trail for workflow Z, integrated via *[SDK/MCP Gateway]*, with p95 decision latency under *N* ms."
- **Mutual Action Plan (MAP):** dated steps with owners on both sides, through to a go/no-go.
- **You pair on integration.** Don't lob a doc over the wall; get to first value in days.
**Exit:** success criteria met + a go/no-go date on the calendar.

### S4→S5 — Paid pilot
Convert validated value into a commercial pilot.

- **Shape:** a fixed-scope, time-boxed paid pilot (3 months) with a clear success definition and a pre-agreed path to annual.
- **Pricing (keep it simple, land-and-expand):** design partner is free + 12 months free; the *paid pilot* is a modest fixed fee (illustratively **$10–25k for a 3-month pilot**, credited toward an annual), or a discounted founder-priced annual. Anchor on value (cost of one prevented bad action / audit-readiness), not seats.
- **Paper:** a one-page pilot order form / SOW, your DPA, and the security packet. Templatize all three.
**Exit:** signed order form. That's your 90-day win.

---

## 4. Handling the enterprise-specific stuff

**Security review (you have no SOC 2 yet — turn it into a strength).** Lead with what you *do* have: the Security & Trust page, the **OWASP AI Exchange / MITRE ATLAS coverage** page, source-available self-host (they can read every line), fail-closed architecture, a DPA, and a pre-filled security questionnaire. Message: "We're early, so you can inspect the whole thing and shape our roadmap — and here's exactly how we map to the frameworks your team uses." Have a short security packet ready to send within an hour of the ask.

**Multi-thread from the start.** A single champion is a single point of failure. By S3, get to the economic buyer and, if regulated, a security/compliance stakeholder. Ask your champion: "Who else needs to be comfortable for this to go to prod?"

**Champion enablement.** Your champion sells internally when you're not in the room. Give them a one-pager, the ROI framing, and the OWASP/MITRE mapping so they can forward it. Make them look smart to their boss.

**Procurement / legal.** Expect a security questionnaire, a DPA, and (sometimes) InfoSec sign-off. Keep templated answers. Don't let a $15k pilot get a $500k contract's paperwork — push for a lightweight pilot agreement.

---

## 5. Messaging & value framework

**The wedge:** *Identity tells you who an agent is; it doesn't decide what the agent is allowed to do.* Kynara is the authorization + approval + audit layer above identity. (Extra timely against the NewCore raise — position them and Okta as integration partners, not rivals.)

**Pain hypotheses to test in discovery:**
- *SecOps/AI-SRE:* "Your agents execute remediation. What proves each action was authorized and reversible when a customer's security team asks?"
- *Regulated:* "When your agent touches money/records, can you prove to an auditor it never exceeded its mandate?"

**Impact framing (help them build the ROI, don't fabricate it):** cost of one prevented bad action (a wrong refund, a leaked record, a bad prod change) + audit/compliance time saved + the risk of shipping agents *without* control. One prevented incident usually dwarfs the pilot fee.

**Objection handling:**
- *"We'll just scope the API token."* Tokens are coarse. They can't express "refunds under $X, business hours, route external recipients to a human." That's the gap.
- *"Isn't this just RBAC?"* RBAC is the gate; the value is ABAC on arguments, non-escalation, approvals, taint-based downgrade, and the audit chain — enforced at the tool boundary, outside the LLM.
- *"You're too early / no SOC 2."* Source-available so you can self-host and inspect; OWASP/MITRE-mapped; design-partner terms; and you shape the roadmap.
- *"Latency?"* Cached reads + local sidecar for sub-ms; a real, disclosed tradeoff.

---

## 6. The 90-day plan

Three 30-day phases. Founder-led means **time-box selling to ~50% of your week** and protect it — the failure mode is disappearing into product.

### Days 1–30 — Foundation + top of funnel
**Build the machine and fill the pipe.**

- Stand up the pipeline (the tracker you have) with the S0–S6 stages; define exit criteria.
- Assemble the sales kit (see §8) from assets you already have: 1-pager, discovery script, 10-min demo script, DP letter, security packet, OWASP/MITRE page.
- Build the 40-account target list (SecOps/AI-SRE first). Send 5 warm-intro asks/week; 15–20 cold touches/week.
- Publish the "identity isn't authorization" content (HN post, LinkedIn) to create inbound.

**Targets:** 40 qualified accounts identified · 12–15 discovery calls held · 6–8 in DP scoping.

### Days 31–60 — Activate design partners + technical validation
**Turn interest into integrated, running deployments.**

- Convert scoping → active design partners; pair on integration (SDK or MCP Gateway) to first value in days.
- Start 2–3 technical validations with **signed success criteria + a MAP**.
- Finalize pilot pricing and the one-page pilot order form.
- Run your first security reviews; refine the security packet from real questions.
- Multi-thread: meet the economic buyer in your top 3 accounts.

**Targets:** 8–10 active design partners · 2–3 POCs running · pilot paper ready · 1 pilot verbally committed.

### Days 61–90 — Land paid pilots + harden the machine
**Close, and make it repeatable.**

- Drive POCs to go/no-go against their success criteria; convert 1–2 to paid pilots.
- Capture a reference outcome / case study (opt-in) from your best design partner.
- Write up the repeatable motion: what worked, conversion rates by stage, the finalized templates.
- Build the day-91 plan: which stage is the bottleneck, and whether a first GTM hire is warranted.

**Targets:** **1–2 signed paid pilots** · 1 case study in progress · documented, repeatable motion + funnel metrics.

---

## 7. Funnel math & weekly scorecard

Illustrative benchmarks for a founder-led, tight-ICP, warm-heavy motion — replace with your actuals as you learn:

| Stage transition | Rough conversion | Volume to hit the goal |
|---|---|---|
| Target → Discovery held | ~30–40% (higher via warm intros) | 40 → ~13 |
| Discovery → DP scoping | ~50% | ~13 → 7 |
| Scoping → Active DP | ~80% | 7 → 6–8 |
| Active DP → POC | ~35% | → 2–3 |
| POC → Paid pilot | ~50% | → **1–2** |

**Weekly scorecard (review every Friday):**
- *Leading:* new qualified accounts added · discovery calls booked/held · scoping calls · POCs started.
- *Lagging:* active design partners · POCs running · paid pilots signed.
- *Health:* stalled deals (no movement 14 days) · single-threaded deals · reply rate on outreach.

Tune messaging weekly on what actually gets replies and advances stages.

---

## 8. The repeatable sales kit (build once, reuse forever)

Repeatability *is* this list. Templatize each; most you already have raw material for.

- **One-pager** — problem, wedge, proof, CTA.
- **Discovery script** — the §3 question bank, in order.
- **10-minute demo script** — the six-beat flow in §3, mapped to pains.
- **Design-partner letter** — ✅ done.
- **POC plan template** — timebox, mutual success criteria, MAP.
- **Security packet** — Security page + OWASP/MITRE page + self-host + DPA + pre-filled security questionnaire.
- **ROI / impact one-pager** — the cost-of-a-bad-action calculator.
- **Pilot order form / SOW** — one page, lightweight.
- **Mutual Action Plan (MAP) template** — dated steps, owners, go/no-go.
- **Follow-up email templates** — post-discovery, post-demo, post-POC, "going dark" nudge.
- **CRM/tracker** — ✅ done; add the S0–S6 stages.

---

## 9. Anti-patterns (how founder-led enterprise sales dies)

- **Chasing logos too big.** A brand-name bank's procurement will outlast your runway. Target Series B–D and innovation/AI-platform teams that can actually sign.
- **Single-threading.** One champion who changes jobs = dead deal. Multi-thread by S3.
- **Free forever.** Design-partner free with no path to paid trains buyers to never pay. The paid pilot is the plan from day one.
- **Bespoke feature promises per prospect.** You'll fracture the product. Feed requests into the roadmap; ship what's broadly useful.
- **Skipping written success criteria.** Verbal "looks great" converts to nothing. Get the POC definition signed.
- **Disappearing into product.** Protect the selling time-box; the pipeline decays without weekly touches.
- **Widening the ICP under pressure.** Slow weeks tempt you to chase non-fits. Don't — it wrecks your funnel math and your calendar.

---

*Next artifacts I can generate on request: the one-pager, the POC plan + Mutual Action Plan templates, the pre-filled security questionnaire, the ROI/impact calculator (as a spreadsheet), and the four follow-up email templates.*
