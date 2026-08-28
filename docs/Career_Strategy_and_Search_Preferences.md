# Career Strategy & Search Preferences — Reference Document

**Owner:** Karthik S R
**Purpose:** Canonical reference for current situation, strategic positioning, and search preferences. This is the document to check before tailoring a resume, answering a recruiter, or evaluating an offer — not a plan to re-litigate each time.

---

## 1. Current Situation

- **Employment status: Not currently employed, effective 14-Aug-2026.** Mutual separation from Ascendion (HP AAVA / OMEN Gaming Hub Analytics Program), executed via signed Mutual Separation Letter — cessation date 14-Aug-2026, business reasons stated (client-side program hold, not performance), notice period paid in lieu rather than served. Final dues settled: accrued salary, leave encashment, ex-gratia, and notice-period pay-in-lieu.
- **This resolves the HP AAVA internal-hold status previously tracked here** (client contact frozen, demos/reviews on hold program-wide since Aug 4, 2026) — the hold ended in separation rather than resumption.
- **Search capacity: full-time.** No employer, no in-office days, no work-hour constraints. Job Search (Track A) can now run as the dominant allocation rather than competing with a day job — see revised Three-Track Model below.
- **Financial runway note:** Final dues provide a buffer, but this is not an indefinite runway — search urgency remains high despite the increased time capacity. Full-time availability is a search advantage, not a reason to slow down.
- **Krapheno status:** Built sufficiently to onboard the first 3 clients; first retainer in progress. **Krapheno remains a secondary track — not paused, not excluded.** It continues to progress independently and is not tied to corporate job timing.

---

## 2. Strategic Positioning

**The correct narrative is specialization, not a pivot:**

> QA Engineer → Data Quality Engineer → Data & AI Platform Quality Engineer → AI Evaluation Engineer → AI Governance / Assurance Engineer

This is an evolution of seven years of existing data-quality expertise, not a jump into a different discipline. Avoid framing interviews or resume language around "learning AI" — frame around "extending data-validation discipline to AI systems," which is what the HP AAVA work actually demonstrates.

**Narrative sentence (use consistently across resume, LinkedIn, interviews):**
> "I have seven years of experience ensuring the quality of data platforms and enterprise systems. At HP, I extended that expertise into agentic AI by engineering and validating multi-agent RCA pipelines with deterministic reasoning, confidence scoring, and guardrails. I'm now specializing in AI evaluation, testing, and governance — helping organizations build AI systems that are reliable, measurable, and production-ready."

---

## 3. Three-Track Model

| Track | Allocation | Status |
|---|---|---|
| **A. Job Search** | 55–65% | Highest priority — full-time search capacity, no employer constraint |
| **B. AI QA Learning** | 25–35% | Ongoing, parallel to search — not a prerequisite to applying |
| **C. Krapheno** | 10–15% | Independent, progressing, not blocking or blocked by A/B |

Tracks A and B run in parallel, not sequentially — the objective is to get interviews now with the current resume, and let learning and interviewing reinforce each other week to week, rather than delaying applications until every evaluation framework is mastered. With full-time capacity, Track A absorbs the time previously spent commuting/in-office (4 days/week) — this should translate into materially higher application volume and interview-prep depth, not just more hours on the same pace.

---

## 4. Track A — Job Search: Preferences & Priorities

### Compensation
- Target: ₹20–30+ LPA
- Last drawn: ₹16 LPA (Ascendion, through 14-Aug-2026)
- Below ₹18 LPA: only if role is otherwise exceptional (e.g., strong AI governance alignment, notable product company)

### Employment Gap / "Why are you looking" Narrative
- Clean, true answer: mutual separation due to a client-side program hold (HP AAVA — client engagement paused program-wide, business reasons), not performance-related. Full dues and separation letter confirm this framing.
- Do not over-explain or volunteer the compressed same-day signing timeline in interviews — it's not relevant to the employer-facing narrative.
- Frame the gap positively where relevant: full-time search capacity means faster onboarding availability for the hiring company — a genuine advantage to surface with recruiters.

### Work Mode — Hard Constraint (not a ranked preference)
Remote is not a weighted trade-off against compensation or role quality — it is a boundary condition on the search itself, on the same footing as the engagement-type exclusion below. Rationale: 2023–2026 experience working hybrid 3–4 days/week (and briefly 2 days/week) demonstrated a direct, recurring cost to time and attention available for parallel long-term work — Kattemane Enterprises, Seed-to-Tree, Krapheno, Pragmedha, and the anthropological research underpinning Pilgrims of Satparva. A brief WFH period during the Happiest Minds-era gap is direct evidence of the difference in capacity available under remote conditions. This is not a hypothetical preference; it is observed from lived experience.

- **Remote or remote-first: required by default.** The fit-scoring/ranking engine should not score hybrid or on-site postings alongside remote ones — they should be filtered out at the same pre-scoring veto stage as engagement type, not weighed against salary or role fit.
- **Hybrid or on-site: excluded by default.** Treated as a named exception requiring explicit case-by-case authorization from Karthik — never surfaced or auto-scored by the ranking engine on its own. An exception is not "high enough compensation" alone; it requires the same kind of exceptional-role justification the sub-₹18 LPA exception already requires (e.g., decisive AI governance alignment, a notable product company, or another factor stated explicitly at the time).
- **Do not collapse this into a scoring dimension.** A high salary number should never be able to outbid this constraint algorithmically. If an otherwise strong hybrid/on-site role appears, it should be flagged for manual review, not auto-ranked into the shortlist.

### Employment Type
- **Full-time employment preferred by default.**
- **Contract acceptable if:** minimum 6-month duration, **and** the engaging company is a **product company, not a service-based/staffing/body-shopping firm.** Short-term or service-based contract placements are not aligned with current goals.

### Company Type
- Preferred: Product companies, AI companies, cloud data companies, SaaS, analytics platforms
- Acceptable: Large enterprises (direct product teams, not staffing arrangements), engineering consulting with a genuine product focus
- Lower priority: Generic IT services, staff augmentation, maintenance-only projects

### Target Search Buckets (use these four, not ten near-synonyms)
1. **AI Quality Engineer** (covers AI Quality / AI Evaluation / AI Assurance titles)
2. **AI Test Automation Engineer**
3. **Data & AI Quality Engineer**
4. **AI Governance / Trust Engineer**

Other titles (AI Reliability Engineer, GenAI Validation Engineer, Senior Data QA Engineer – AI Platforms, etc.) are resume/LinkedIn keyword variants, not separate search terms.

### Explicit Exclusions
- Selenium-only, Cypress-only, Playwright-only, UI-heavy QA roles
- Mobile QA, WordPress QA, manual-testing-only roles

---

## 5. Track B — AI QA Learning

Reference: `AI_QA_Learning_Roadmap_Scope.md` (baseline document — scope is considered correct and complete; do not add new major topics without a deliberate scope decision).

**Execution mindset:** weekly incremental progress alongside active interviewing, not "finish everything, then apply." Example cadence:
- Week 1: DeepEval basics + apply to ~20 companies
- Week 2: Promptfoo + continue interviews
- Week 3: Ragas + advance the GitHub evaluation suite project

**Priority order (unchanged from baseline):**
1. LLM core six metrics (faithfulness, groundedness, hallucination rate, answer relevancy, context precision, context recall) — fluency with concrete examples, ideally mapped to AAVA specifics.
2. DeepEval → Promptfoo → Ragas, in that order.
3. Agent evaluation metrics (task completion, tool success rate, retry rate, planning accuracy) mapped to specific AAVA pipeline details.
4. GitHub "AI Quality Evaluation Suite" project — the flagship deliverable that makes the above demonstrable rather than claimed.

**One skill to build quietly, beyond the baseline:** evaluation dataset design — representative eval sets, avoiding prompt-overfitting to the eval set, versioning golden test cases, measuring regression over time. This is the engineering mindset differentiator behind AI quality work, and it builds directly on existing QA background.

**Explicitly out of scope:** training foundation models, CUDA/distributed GPU programming, transformer architecture research, RLHF implementation, biosecurity/nuclear risk evaluation.

### 5.1 Why the GitHub Project Uses Job-Search Data

The flagship AI Quality Evaluation Suite (see `AI_QA_Learning_Roadmap_Scope.md` §1.6)
uses the resume PDF and JobOps SQLite database as its evaluation corpus
instead of a synthetic dataset. Rationale:

- Real resume + real JobOps data means ground truth is known, making
  evaluation results meaningful rather than illustrative.
- Produces practical value during the active search, not just a portfolio
  artifact.
- Demonstrates AI Quality Engineering, RAG, SQL, hybrid retrieval,
  evaluation metrics, and Python engineering in one coherent project.
- Self-renewing eval set: every new job posting and every resume revision
  becomes another evaluation case, without manual dataset upkeep.

---

## 6. Track C — Krapheno

- Genuinely built and capable of onboarding real clients — not a side experiment.
- **Deliberately kept separate from the corporate job search.** Do not force Krapheno into interview narratives; do not let Krapheno's timeline affect financial decisions about the corporate role.
- Recurring-revenue gate before Krapheno is treated as a stability source: **$2,000/month or more.**
- Corporate role provides stability; Krapheno builds long-term equity. Complementary tracks, evaluated independently.
- Convergence between the two tracks is expected to be staggered, occurring only once Krapheno reaches stable recurring revenue with multiple clients — not planned or forced on a fixed timeline.

---

## 7. Current Skills Assessment

| Area | Status |
|---|---|
| Data Engineering QA (ETL, SQL, migration, profiling) | Excellent |
| SQL & ETL | Excellent |
| Python Automation (Pytest, Pandas, SQLAlchemy) | Strong |
| Cloud Data Platforms (Redshift, Databricks, Snowflake) | Strong |
| Agentic AI Exposure (AAVA multi-agent RCA pipeline) | Strong — primary differentiator |
| Leadership & Communication | Strong |
| AI Evaluation Tooling (DeepEval/Promptfoo/Ragas) | Developing — roadmap in place |
| Portfolio / GitHub (evaluation suite project) | Needs completion — highest-leverage gap |
| ML Theory | Sufficient for target roles — no deeper study needed |
| AI Governance Concepts | Strong conceptual foundation (via Krapheno) |

**The single most consequential gap:** a finished AI evaluation project. Not because target employers expect framework mastery, but because a completed project makes the AAVA experience verifiable rather than just claimed.

---

## 8. Priority Action Sequence

1. Apply at full-time-search volume, using the current resume (Resume v3.0) — do not wait for the learning roadmap to complete.
2. Build the AI Quality Evaluation Suite GitHub project as the flagship portfolio piece, in parallel with applying — full-time capacity should accelerate this toward Milestone 2A/2B completion.
3. Use each interview to refine the narrative and identify genuine (not assumed) knowledge gaps.
4. Keep the employment-gap narrative simple and consistent (Section 4) — mutual separation, business reasons, immediate availability as an asset.
5. Keep Krapheno progressing independently — do not tie financial stability or job-search urgency to its timeline.

---

*This document should be updated when: HP AAVA status changes materially, Krapheno crosses the $2,000/month recurring-revenue gate, or search preferences (comp, remote/contract terms, target titles) change. Otherwise, treat it as settled.*

*Last material update: August 28, 2026 — Work Mode (Section 4) reclassified from a ranked preference ("Hybrid — acceptable") to a hard constraint. Remote/remote-first is now required by default; hybrid/on-site is excluded from automated fit-scoring entirely and requires explicit case-by-case authorization, on the same footing as the third-party/staffing engagement-type exclusion. Rationale: 2023–2026 hybrid work history (3–4 days/week, briefly 2 days/week) showed direct, recurring cost to time available for Kattemane Enterprises, Seed-to-Tree, Krapheno, Pragmedha, and the anthropological research feeding Pilgrims of Satparva; a brief WFH period during the Happiest Minds-era gap evidenced the contrast directly.*

*Previous update: August 14, 2026 — Mutual separation from Ascendion executed (cessation date 14-Aug-2026, business reasons, notice period paid in lieu). This resolves the Aug 4, 2026 HP AAVA internal-hold status previously tracked here. Employment status changed from employed/searching-in-parallel to full-time job search; Track A allocation increased accordingly (Section 3), and an employment-gap narrative was added (Section 4).*
