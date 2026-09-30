# JOBOPS_SCALING_EXECUTION_PLAN.md

**Type:** Execution Plan — **PLANNING ARTIFACT ONLY, NO IMPLEMENTATION**
**Repository:** `~/projects/jobs-application-automation` (JobOps)
**Plan date:** 2026-08-28
**JobOps HEAD:** `02c6a81` — *phase1: log Search 001, pause manual GitHub-browsing approach*, branch `main`
**Working tree at planning time:** ` M data/jobs-tracker.db` · `?? JOBOPS_SCALING_CAPABILITY_INVENTORY.md` · `?? docs/Career_Strategy_and_Search_Preferences.md`
**Evidence base:** `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` (1,138 lines, 2026-08-28)
**Supersedes:** nothing. Amends nothing. Decides nothing.

> **Standing.** This document is a **proposal**. It converts no proposal into a decision. Where the inventory recorded an `OWNER RULING REQUIRED`, this plan records whether that ruling has since become answerable from committed repository evidence — and where it has not, it leaves it open. Per `ai-quality-engineering/docs/PROJECT_ORIENTATION.md` §6, *"Agents propose, the Repository Owner decides."*

---

## 0. Input Reconciliation — what was and was not available

| Named input | Status | Effect on this plan |
|---|---|---|
| JobOps repository | ✅ Read | Baseline |
| `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` | ✅ Read | Sole evidence base; findings F1–F5 carried forward |
| **Career Strategy / Search Preferences material** | ✅ **PRESENT — and this is new** | `docs/Career_Strategy_and_Search_Preferences.md`, 164 lines, *"Last material update: August 28, 2026"*. **It did not exist when the inventory was produced.** It materially resolves or narrows OR-01…OR-07. See §1.1 and §2.2. |
| **Planning discussion `Pasted markdown(20260828-140604).md`** | ❌ **NOT FOUND** | `find ~ -iname "*Pasted*markdown*" -o -iname "*20260828*"` returns nothing. **No proposed direction from that discussion is incorporated.** Any direction it contained that is not in this prompt or in the repository is absent from this plan. If it matters, it must be supplied. |
| `docs/INDEX.md`, `docs/SYSTEM_SUMMARY.md`, `docs/COMPANY_RADAR_EXPERIMENT.md`, `docs/reports/`, `migrations/` | ✅ Read | Governance constraints; CONFLICT-1…CONFLICT-4 |
| `ai-quality-engineering/docs/PROJECT_ORIENTATION.md`, `docs/DEFERRED_ITEMS_REGISTER.md` | ✅ Read | Boundary + register style |
| `~/projects/ai-job-search` | ✅ Read | Architectural reference only |

**Owner policy in the task prompt** is treated as a **proposed target state**, per instruction — marked `OWNER RULING` throughout, never as adopted. Where the prompt and the newly-present career document **disagree**, that disagreement is surfaced (OR-03) rather than reconciled by me.

---

## 1. Executive Decision

### 1.1 The decision this plan asks for

**Ship P0 = a trustworthy, measurable, preference-gated candidate queue. Nothing else.**

The single most important change since the capability inventory: **`docs/Career_Strategy_and_Search_Preferences.md` now exists in the repository.** The inventory's headline finding was that this document was absent, which forced every career criterion to `UNKNOWN / OWNER RULING REQUIRED`. That is no longer true.

The document is not merely present — **it is unusually prescriptive about exactly the mechanism P0 needs.** §4 *Work Mode* states, in the owner's own words:

> *"The fit-scoring/ranking engine should not score hybrid or on-site postings alongside remote ones — they should be filtered out at the same **pre-scoring veto stage** as engagement type, not weighed against salary or role fit."*
>
> *"**Do not collapse this into a scoring dimension.** A high salary number should never be able to outbid this constraint algorithmically. If an otherwise strong hybrid/on-site role appears, it should be **flagged for manual review, not auto-ranked** into the shortlist."*

That is a direct, dated, owner-authored specification of the P0 gate: a pre-scoring veto stage, `FAIL` excludes from ranking, exception cases surface as flagged-for-review rather than auto-ranked. **It is also a direct statement that the current implementation violates policy** — inventory finding **F3** established that `simple_scorer.py` can penalise any deal-breaker by at most **−5.0 points out of 100**, which is precisely the "collapse into a scoring dimension" the document forbids.

**P0 is therefore no longer blocked on policy discovery. It is blocked on four narrow rulings and four governance conflicts**, listed in §3.

### 1.2 What changed since the inventory — three material deltas

| Δ | Change | Consequence |
|---|---|---|
| **Δ1** | `docs/Career_Strategy_and_Search_Preferences.md` exists | OR-01 substantially resolved; OR-02, OR-05, OR-06, OR-07 resolved or narrowed; OR-03, OR-04 narrowed to precise residual questions |
| **Δ2** | The document is **untracked in git** (`??`) and **referenced by no governance document** — `grep -rn "Career_Strategy" docs/ README.md CLAUDE.md` returns nothing outside the file itself | The authoritative policy artifact is one `rm` from gone and invisible to `docs/INDEX.md`. **New conflict: CONFLICT-9.** |
| **Δ3** | `data/jobs-tracker.db` is now modified in the working tree | Caused by the inventory's read-only `sqlite3` queries checkpointing the WAL sidecar into the tracked main file. Row counts verified identical; **no data written**. It is *evidence for* CONFLICT-3, not a new defect. `git checkout` on it would **discard** committed transactions that had lived only in the WAL — do not do that casually. |

### 1.3 The P0 thesis, unchanged by Δ1

The strategic objective is **quality-adjusted opportunities per unit of candidate time**, not raw job count. The inventory established that:

- automated discovery currently yields **zero** candidates to the human (F1: scraper last ran 2025-11-14, 77 rows, all LOW/NO_FIT);
- the one automated discovery→pipeline bridge **has never executed** (F2: `opportunities.scraped_job_id` does not exist);
- hard vetoes are **arithmetically impossible** (F3);
- unknowns are scored as **favourable** (F4);
- four of eight funnel stages have **no schema representation** (F5).

Raising ingestion volume before fixing F3/F4 would spend the candidate's scarcest resource — attention — on exactly the postings the newly-present policy exists to reject. The career document names the same failure mode from the other direction (§4: a high salary must never outbid the remote constraint algorithmically).

**P0 exists to make the gate real, the unknowns honest, and the funnel measurable. That is the whole of it.**

### 1.4 A throughput reality the Owner should confront before approving

Two figures now sit in tension, and the plan does not resolve them:

- The task prompt sets a target of **~25–30 quality opportunities/applications per day**.
- `docs/Career_Strategy_and_Search_Preferences.md` §5, the only volume figure in the authoritative document, gives an example cadence of **"apply to ~20 companies"** in *Week 1* — roughly **3–4/day**.
- The repository records **10 applications total**, best single day **7** (2026-08-20), then 8 days with none.
- §3 allocates **55–65%** of capacity to Track A, alongside Track B (25–35%) and Track C (10–15%).

25–30/day is roughly **7–10× the cadence the authoritative document itself describes**, sustained. This may be entirely intentional given §1's *"full-time search capacity… materially higher application volume"* — but it is not what the document says, and no per-application time cost is measured anywhere in JobOps.

**This is why per-candidate time instrumentation (P0-10) is in P0 and not deferred.** Without it, no phase transition in this plan is falsifiable, and the 25–30 target cannot be distinguished from an aspiration. **OR-09 and OR-10 remain open.**

---

## 2. Verified Current State

Separated per instruction into `VERIFIED` / `OWNER DECISION REQUIRED` / `PROPOSED`. Nothing in this section was repaired or modified.

### 2.1 VERIFIED CURRENT STATE — repository facts

Carried from the capability inventory, re-checked today where cheap to do so without touching the database.

| # | Verified fact | Evidence |
|---|---|---|
| V1 | **Automated discovery yields zero applications.** RemoteOK scraper ran once (2025-11-14), 77 rows, 9 LOW_FIT / 68 NO_FIT, none HIGH_FIT | Inventory F1 |
| V2 | **The discovery→opportunity bridge has never executed.** `POST /api/import-scraped-job/{id}` reads/writes `opportunities.scraped_job_id`; column absent; migration `005` unapplied; all 77 rows `imported_to_opportunities = 0` | Inventory F2 |
| V3 | **Hard vetoes are structurally impossible.** `red_flag_penalty` floors at −50, weighted 0.10 ⇒ **max −5.0 points on a 0–100 scale** | Inventory F3; `scrapers/simple_scorer.py` |
| V4 | **Unknown is scored as favourable.** Empty experience ⇒ 100; empty location ⇒ 50; `domain_match DEFAULT 'Good'`; `is_remote BOOLEAN` cannot hold unknown; **salary is not a scoring dimension at all** | Inventory F4 |
| V5 | **Four of eight funnel stages have no schema representation**, and `opportunities` carries **zero indexes** — no uniqueness on `job_url` or `(company, role)` | Inventory F5 |
| V6 | **No migration system.** `PRAGMA user_version = 0`; no history table; `004` and `005` unapplied; runtime DDL in `remoteok_integration.py` is a fourth schema channel | `docs/reports/migration-architecural-audit.md`; inventory §2.1.3 |
| V7 | **Two independent write paths to the system of record.** `api-server.py` (parameterised) and n8n workflow 06 (`executeCommand` + string-concatenated SQL, hand-rolled `escapeSql`) | Inventory §2.1.7 |
| V8 | **No auth on the API**, `Access-Control-Allow-Origin: *`; n8n basic-auth default password committed in `docker-compose.yml` | Inventory §2.1.6 |
| V9 | **No Naukri code anywhere** in JobOps or `ai-job-search` — only TODOs, a dropped CHECK enum value, a dashboard dropdown option, a `job_sources` row | Inventory §2.1.4, §4.A.1 |
| V10 | **No LinkedIn ingestion in JobOps.** `ai-job-search/.agents/skills/linkedin-search` exists, is country-agnostic, `bun`-only, credential-free, unit-tested, and ships a Bengaluru example | Inventory §2.3.2 |
| V11 | **No CV / cover-letter / PDF / ATS capability of any kind in JobOps.** `documents` table: 0 rows. `prompts/` is read by no code | Inventory §2.1.9 |
| V12 | **Outcome corpus is 10 applications, 1 resolved, 8 days old.** `interactions`: 3 rows, all 2025-10-31 seed, all `sentiment='Unknown'` | Inventory §2.1.8, §4.F |
| V13 | **`ai-job-search` has never been run.** `CLAUDE.md` all `[PLACEHOLDER]`; `job_scraper/` = `.gitkeep`; no `job_search_tracker.csv`. Its mechanisms are **specification text, not observed behaviour** | Inventory §2.3.1 |
| V14 | **`COMPANY_RADAR_EXPERIMENT.md` §7 Channel E defers LinkedIn discovery "indefinitely — verification-only role."** §3 and §10 restate it. Phase 1 is open and paused | Inventory §2.1.10 |
| V15 | **`data/jobs-tracker.db` is tracked in git** and now shows modified (WAL checkpoint, no data change) | Inventory CONFLICT-3; `git status` |

### 2.2 VERIFIED CURRENT STATE — the career policy document (NEW)

`docs/Career_Strategy_and_Search_Preferences.md`, 164 lines, self-described *"Canonical reference… not a plan to re-litigate each time"*, *"Last material update: August 28, 2026"*.

**What it settles, quoted:**

| Policy area | Document text | Gate implication |
|---|---|---|
| **Work mode** | *"Remote or remote-first: required by default."* *"Hybrid or on-site: excluded by default. Treated as a named exception requiring explicit case-by-case authorization from Karthik — never surfaced or auto-scored by the ranking engine on its own."* *"filtered out at the same pre-scoring veto stage as engagement type"* *"Do not collapse this into a scoring dimension."* *"flagged for manual review, not auto-ranked into the shortlist"* | **Hard veto, pre-scoring. Exception lane = flagged-for-review, never auto-ranked.** The most directly implementable rule in the document. |
| **Compensation** | *"Target: ₹20–30+ LPA"*; *"Last drawn: ₹16 LPA"*; *"Below ₹18 LPA: only if role is otherwise exceptional (e.g., strong AI governance alignment, notable product company)"* | **Exception line stated at ₹18 LPA; target band ₹20–30+.** Salary **UNKNOWN is not addressed at all.** |
| **Employment type** | *"Full-time employment preferred by default."* *"Contract acceptable if: minimum 6-month duration, **and** the engaging company is a product company, not a service-based/staffing/body-shopping firm."* *"Short-term or service-based contract placements are not aligned with current goals."* | **Contract duration threshold EXISTS: ≥6 months, conjunctive with product-company.** No invention required. Unknown duration not addressed. |
| **Company type** | Preferred: product / AI / cloud data / SaaS / analytics. Acceptable: large enterprises (direct product teams, not staffing arrangements), engineering consulting with genuine product focus. *"Lower priority: Generic IT services, staff augmentation, maintenance-only projects"* | **"Lower priority" is soft language** — see OR-04 residual. |
| **Role targeting** | Four buckets: **AI Quality Engineer**, **AI Test Automation Engineer**, **Data & AI Quality Engineer**, **AI Governance / Trust Engineer**. *"Other titles … are resume/LinkedIn keyword variants, not separate search terms."* | **Explicit, closed list of four.** Framed as *search terms*, not stated as an eligibility filter — see OR-02 residual. |
| **Technology exclusions** | *"Selenium-only, Cypress-only, Playwright-only, UI-heavy QA roles"*; *"Mobile QA, WordPress QA, manual-testing-only roles"* | **Playwright and mobile policy now exist** (the inventory found none). The `-only` qualifier is explicit and load-bearing. **WordPress QA is new** — absent from `resume_config.json` entirely. |
| **Positioning** | *"specialization, not a pivot"*: QA → Data Quality → Data & AI Platform Quality → AI Evaluation → AI Governance | Supports treating Data/ETL QA as adjacent-compatible, not as a discarded family |
| **Capacity** | Track A (job search) **55–65%**; Track B (learning) 25–35%; Track C (Krapheno) 10–15%. Full-time search since 14-Aug-2026 | The candidate-time budget P0-10 must measure against |
| **Boundary intent** | §5.1: the `ai-quality-engineering` flagship suite *"uses the resume PDF and JobOps SQLite database as its evaluation corpus"*; *"every new job posting … becomes another evaluation case"* | **Owner-stated intent that AIQE consumes JobOps data.** Confirms the read-only-consumer boundary and gives P0's schema a second stakeholder |

**What it does NOT settle:** salary-unknown semantics; unknown-duration semantics; whether the four buckets gate eligibility or only seed search queries; whether a *full-time* staffing-firm role is excluded or merely deprioritised; the operational test for "-only"; LinkedIn ingestion permissibility; the throughput baseline and target.

**Two structural problems with the document itself:**

- **It is untracked** (`?? docs/Career_Strategy_and_Search_Preferences.md`, no git history). → **CONFLICT-9.**
- **It cites `AI_QA_Learning_Roadmap_Scope.md` as a "baseline document" (§5, §5.1) — and that file does not exist anywhere under `~`.** This is the same class of dangling provenance citation that `ai-quality-engineering/docs/DEFERRED_ITEMS_REGISTER.md` §8 **NA-06** records for four other documents, including this one. Recorded, not repaired.

### 2.3 OWNER DECISION REQUIRED

Ten rulings and five conflicts, tabulated in §3. Four rulings are **P0-blocking**: OR-03 (salary-unknown), OR-04 (staffing scope), OR-08 (LinkedIn), and CONFLICT-2 (migration authority).

### 2.4 PROPOSED ARCHITECTURE

§12. Summary: a **pre-scoring policy gate** producing `PASS` / `FAIL` / `UNKNOWN` / `EXCEPTION-FLAG`, reading a **versioned policy artifact derived from the career document**, writing verdicts with **rule id + verbatim triggering evidence**, feeding a **candidate queue** that is upstream of `opportunities`. Ingestion is a subprocess boundary. `opportunities` remains the *application* record.

### 2.5 IMPLEMENTATION TASK

§4 (P0-01…P0-10). No implementation is performed by this document.

### 2.6 PARKED BACKLOG

§6 (P1), §7 (P2), §8 (Gmail/n8n), §9 (P3/P4). Traceability to `JS-01…JS-28` in §14.

### 2.7 PERMANENTLY REJECTED

§10 (`JS-R1…JS-R5`). Recorded, never backlogged.

---

## 3. Owner Rulings Required

### 3.1 Career-policy rulings — status after the career document landed

| id | Ruling | Status now | Residual question the Owner must answer | P0-blocking? |
|---|---|---|---|---|
| **OR-01** | Authoritative career policy artifact | **SUBSTANTIALLY RESOLVED** — `docs/Career_Strategy_and_Search_Preferences.md` exists, self-declares canonical, dated 2026-08-28 | (a) Confirm it is authoritative **over `data/resume_config.json`**, which disagrees on salary (₹18L `min_salary_inr`) and role family (QA-Lead/ETL). (b) Is `resume_config.json` to be **regenerated from** it, or retired? (c) **Commit it** and register it in `docs/INDEX.md` — see CONFLICT-9 | **YES** (b) |
| **OR-02** | Role-family scope | **RESOLVED as a search-term list** — four named buckets; other titles explicitly *"keyword variants, not separate search terms"* | Are the four buckets **also an eligibility gate** (a posting outside them FAILs), or **only query seeds** (a posting outside them is still eligible if it passes every other rule)? §2 *"specialization, not a pivot"* and bucket 3 *"Data & AI Quality Engineer"* argue for the latter; the prompt's *"do not silently discard relevant QA/Data/ETL opportunities"* argues the same. **Not decided here** | NO — P0 can seed queries from the buckets without gating on them |
| **OR-03** | ₹20 LPA floor and unknown-salary treatment | **PARTIALLY RESOLVED — and the prompt and the document disagree** | (a) The **task prompt** says *"Current target floor: ₹20 LPA"*. The **document** says *"Target: ₹20–30+ LPA"* but sets the exception line at *"Below ₹18 LPA: only if role is otherwise exceptional."* **Which is the veto threshold — ₹18L or ₹20L?** The ₹18–20L band is currently unclassified by both. (b) **The document is silent on unknown salary.** The prompt states *"Salary UNKNOWN must never be treated as salary PASS"* — confirm as ruling. (c) Is unknown-salary `UNKNOWN` (queue, surface, do not auto-shortlist) or `FAIL`? Most Indian postings state no salary, so this choice largely determines P0 queue volume | **YES** |
| **OR-04** | Third-party / staffing treatment | **PARTIALLY RESOLVED — genuine internal ambiguity in the document** | The document states a **hard exclusion only inside the contract clause** (*"the engaging company is a product company, not a service-based/staffing/body-shopping firm"*), while the Company Type section calls staff augmentation *"Lower priority"* — soft language. §4 Work Mode separately refers to *"the engagement-type exclusion below"* as an established hard veto. **Is a full-time role at a staffing/services firm `FAIL`, or a low-scoring `PASS`?** The prompt proposes `FAIL` by default | **YES** |
| **OR-05** | Technology / role exclusions | **RESOLVED as policy; open as an operational test** | Policy list is explicit: Selenium-only, Cypress-only, Playwright-only, UI-heavy, Mobile QA, WordPress QA, manual-testing-only. **What evidence pattern makes a posting "-only"?** (e.g. tool named as sole automation stack; no data/SQL/API/AI-eval signal present; explicit "manual testing" framing). Note the current `resume_config.json` contradicts the policy: bare `Selenium` scores **+4** as a nice-to-have while `Selenium UI` scores −12 | NO — P0 can ship the mechanism with a first-cut rule and a named test case, provided the rule is versioned data |
| **OR-06** | Remote / hybrid / on-site | **✅ FULLY RESOLVED, and prescriptively so** | None. The document specifies the rule *and* the mechanism: pre-scoring veto stage, never a scoring dimension, hybrid/on-site excluded by default, exception requires explicit per-opportunity authorization, exception cases *"flagged for manual review, not auto-ranked into the shortlist"* | NO — this is the P0 reference implementation |
| **OR-07** | Contract-duration rules | **RESOLVED — threshold exists, no invention needed** | Rule is conjunctive: **≥6 months AND product company**. Residual: how is **unknown duration** treated — `UNKNOWN` or `FAIL`? And does the ≥6-month test apply to a full-time permanent role at all (presumably not)? | NO — but the unknown-duration semantic rides on OR-03(c) |
| **OR-08** | LinkedIn ingestion scope | **UNRESOLVED — unchanged since the inventory** | Does `COMPANY_RADAR_EXPERIMENT.md` §7 Channel E (*"deferred indefinitely — verification-only role"*) bar LinkedIn **ingestion in JobOps generally**, or scope only the Company Radar experiment? Compounded by `linkedin-search`'s own *"⚠️ Personal use only — against LinkedIn's ToS"* notice. **This ruling selects P0's ingestion path** — see §4.2 | **YES** |
| **OR-09** | Definition of the "~15/day" baseline | **UNRESOLVED — and now contradicted a second way** | Repository records 10 applications, best day 7. The career document §5 example cadence is *"apply to ~20 companies"* per week (~3–4/day). **What did ~15/day count, over what period, recorded where?** Treated throughout this plan as an **owner-defined operational baseline, not a measured fact** | NO — but it blocks any claim that a phase improved throughput |
| **OR-10** | Definition of the 25–30/day target | **UNRESOLVED** | Is 25–30 **applications submitted/day**, or **qualified opportunities surfaced for review/day**? These imply materially different systems: the first is bounded by form-completion time, the second by ingestion and gate throughput. Given §3's 55–65% Track A allocation and the §5 ~20/week cadence, the second reading is far more consistent with the authoritative document | NO for P0 scope; **YES** before any P2 sizing |

### 3.2 Architecture / governance conflicts

| id | Conflict | Why it matters to P0 | Ruling required | P0-blocking? |
|---|---|---|---|---|
| **CONFLICT-1** | **n8n / SQLite write boundary.** Workflow 06 writes `INSERT INTO opportunities` via `executeCommand` + string-concatenated SQL with hand-rolled `escapeSql`, bypassing the parameterised REST API. Contradicts `CHANGELOG.md` v2.0.0's *"Parameterized all SQL queries"* claim | P0 introduces a **new write path** (gate verdicts, queue state). Without a ruling it becomes a third | Is the REST API the **sole** authorized writer to `data/jobs-tracker.db`? If yes, is workflow 06 retired or rewritten to call the API? | **Strongly advised before P0 code**; P0 can be *designed* against the API-sole assumption |
| **CONFLICT-2** | **Migration authority.** No runner, no history table, `user_version = 0`; `004` and `005` unapplied; runtime DDL in `remoteok_integration.py`; the applied set is not derivable from the database | Every P0 capability needs schema. Repairing F2 is a non-idempotent `ALTER TABLE` against a database of unknown migration state | (a) Who may apply a migration, by what procedure? (b) Is a runner + history table a **P0 prerequisite** (recommended) or P0 scope? (c) Is applying `005` authorized to repair F2? (d) Disposition of unapplied `004`? (e) Does the runtime DDL stay? | **YES — hard blocker** |
| **CONFLICT-3** | **Tracked runtime SQLite database.** `data/jobs-tracker.db` is git-tracked; ~40% of live schema has no SQL artifact; the file is currently modified by a WAL checkpoint from read-only queries | At P0 ingestion rates every run produces a binary diff, and a schema change becomes indistinguishable from a data change | Untrack the runtime DB (committing a seed/fixture instead)? If yes, is that a P0 prerequisite? **Note:** `git checkout data/jobs-tracker.db` would discard WAL-resident transactions — do not use it as the cleanup | **Strongly advised before P0** |
| **CONFLICT-8** | **No API authentication.** `Access-Control-Allow-Origin: *`, no auth; n8n basic-auth default password committed in `docker-compose.yml` | Not a throughput blocker, but P0 is the moment this database becomes the system of record for the entire search at automated volume | Required before P0, or accepted as localhost-only with the credential rotated? | NO — but decide explicitly rather than by omission |
| **CONFLICT-9** | **NEW — the authoritative policy artifact is untracked and unregistered.** `docs/Career_Strategy_and_Search_Preferences.md` has no git history and is referenced by no governance document (`grep` over `docs/`, `README.md`, `CLAUDE.md` returns nothing). It additionally cites `AI_QA_Learning_Roadmap_Scope.md`, which does not exist anywhere | P0 derives its entire ruleset from this file. An uncommitted, unregistered authority is one `rm` from gone, and cannot be versioned against gate behaviour | (a) Commit it. (b) Register it in `docs/INDEX.md`. (c) Confirm supersession over `data/resume_config.json`. (d) Disposition of the dangling `AI_QA_Learning_Roadmap_Scope.md` citation — supply, or record as NA-06-class provenance | **YES — commit before P0 code** |

### 3.3 The four hard P0 blockers, isolated

Nothing in P0 should start until these are answered:

1. **OR-03** — salary veto threshold (₹18L or ₹20L) **and** unknown-salary semantics.
2. **OR-04** — is full-time-at-a-staffing-firm `FAIL` or low-scoring `PASS`?
3. **OR-08** — is LinkedIn ingestion permitted in JobOps?
4. **CONFLICT-2** — migration authority, and specifically whether applying `005` is authorized.

Plus one that is cheap and should simply be done: **CONFLICT-9(a)** — commit the career document.

---
## 4. P0 Execution Plan — Trustworthy Candidate Funnel

**P0 objective:** turn JobOps from a partially functioning discovery/tracking system into a **trustworthy, measurable, preference-gated candidate queue.**

**P0 is complete when a human can trust the queue.** Not when the queue is large, not when it is automated, and not when it is well-ranked — ranking is P1. Trust means: every candidate in the queue passed a deterministic, tested, versioned policy gate derived from `docs/Career_Strategy_and_Search_Preferences.md`; every candidate excluded carries a machine-readable reason and the verbatim posting text that triggered it; and nothing unknown was silently treated as acceptable.

### 4.1 P0 task table

| Pri | Capability / task | Class | Dependency | Reason | Acceptance criterion | Owner decision? | JS / OR / CONFLICT |
|---|---|---|---|---|---|---|---|
| **P0-01** | **Authoritative policy artifact** — commit `docs/Career_Strategy_and_Search_Preferences.md`; register in `docs/INDEX.md`; derive a **versioned, machine-readable policy ruleset** from its §4; declare supersession over `data/resume_config.json` | **Existing (doc) + New Build (ruleset)** | CONFLICT-9; OR-01; OR-03; OR-04 | Every other P0 task reads this. An untracked authority cannot be versioned against gate behaviour, and `resume_config.json` currently **contradicts** it on salary and role family | Career doc committed and INDEX-registered; a versioned ruleset file exists whose every rule cites a §-reference in the career doc; `resume_config.json`'s status (regenerated / retired / demoted to scoring-only) is recorded | **YES** | JS-04 · OR-01/02/03/04/05/06/07 · CONFLICT-9 |
| **P0-02** | **Deterministic preference gate** — runs **before** scoring; emits a verdict per rule; never a weighted term | **New Build** *(architecture adapted from `04-job-evaluation.md` Gates + `/rank` Rule 4)* | P0-01 | The career doc §4 **specifies this mechanism directly**: *"filtered out at the same pre-scoring veto stage"*, *"Do not collapse this into a scoring dimension."* F3 proves the current scorer cannot express it (−5.0 pt ceiling) | Same posting + same ruleset version ⇒ byte-identical verdict, repeatably. Gate runs and can exclude **with no scorer invoked at all**. Every `FAIL` carries rule id + verbatim triggering text | NO *(mechanism)* / **YES** *(rule content — OR-03, OR-04)* | JS-04 · OR-04/05/06/07 · JS-R5 |
| **P0-03** | **PASS / FAIL / UNKNOWN / EXCEPTION-FLAG semantics** — four verdict values, not two | **New Build** | P0-02 | The career doc needs all four: remote ⇒ `PASS`/`FAIL`; hybrid/on-site ⇒ excluded but *"flagged for manual review, not auto-ranked"* ⇒ `EXCEPTION-FLAG`; sub-₹18L and <6-month contract ⇒ same exception lane; missing salary ⇒ `UNKNOWN` | All four values are representable, persisted, and independently queryable. An `EXCEPTION-FLAG` candidate **never enters the ranked shortlist** and always appears in the review lane | NO *(mechanism)* | JS-04 · OR-03/06/07 |
| **P0-04** | **Correct unknown handling** — unknown ≠ absent ≠ known; unknown is never favourable | **New Build** *(rule adapted from `/rank` Step 3 r6: "never infer, never backfill")* | P0-03; OR-03(c) | F4 is the defect that would make a gated queue untrustworthy: empty experience ⇒ 100, empty location ⇒ 50, `domain_match DEFAULT 'Good'`, salary never read. Fixing the gate without fixing this just moves the lie upstream | A posting with no stated salary, no stated work mode and no stated employer type yields **three `UNKNOWN`s**, contributes **zero** favourable signal, and is presented as *unassessed* — not as a good fit. Regression test asserts the F4 cases specifically | **YES** — OR-03(c) sets whether unknown-salary is `UNKNOWN` or `FAIL` | JS-04 · OR-03 · F4 |
| **P0-05** | **Discovery→opportunity bridge repair** — make `POST /api/import-scraped-job/{id}` executable | **Existing (defect repair)** | **CONFLICT-2 (hard blocker)** | F2: the only automated path into the system of record has **never run once**. Every downstream P0 capability terminates in a dead end without it. The endpoint code is already correct — transactional, idempotent, `409` on re-import | A scraped candidate imports to `opportunities` end-to-end and returns `200`; a second attempt returns `409`; `imported_to_opportunities` flips; provenance is queryable both directions | **YES** — who applies migration `005`, and by what procedure | JS-04 · CONFLICT-2 · F2 |
| **P0-06** | **Minimum one-source ingestion** — exactly one source, gated by OR-08 | **Adapt (A) or Existing-Extend (B)** — see §4.2 | **OR-08 (hard blocker)** | The gate needs live input to be provable. One source, not two: a second portal before the first proves throughput violates `COMPANY_RADAR_EXPERIMENT.md` §9's hard rule | ≥1 fetch run produces candidates carrying title, company, URL, location, work-mode signal, posting date, and JD text sufficient for the gate to reach a non-`UNKNOWN` verdict on **work mode** at minimum | **YES** — OR-08 | JS-01(not this) · OR-08 · CONFLICT-4 |
| **P0-07** | **Cross-source-safe dedup foundation** | **Adapt** *(`/scrape` Step 4 key strategy: normalised URL **or** company+title)* | P0-06 | Built now, not later, because retrofitting dedup after duplicates are in the system of record is a data-repair problem. `scraped_jobs.external_id UNIQUE` dedups **within RemoteOK only**; `opportunities` has **zero indexes** (F5) | Re-running ingestion twice adds zero duplicate candidates; a candidate already in `opportunities` is not re-queued; the key strategy is source-agnostic by construction and demonstrated against a synthetic second source | NO | JS-06 · F5 |
| **P0-08** | **Candidate review queue** — shortlist / below-threshold / **excluded-with-reason** | **Extend** *(`GET /api/scraped-jobs` + dashboard already render score, matched skills/domains, red flags; presentation adapted from `/rank` Step 5)* | P0-03, P0-07 | This is where "trustworthy" becomes visible. Real reuse: the read path, the filters and the rationale payload already exist. The career doc requires an exception lane that is **surfaced but never auto-ranked** | The human sees three lanes; every excluded candidate shows its rule id and quoted trigger; every `EXCEPTION-FLAG` appears in the review lane and in **no** shortlist; every row links to `job_url` | NO | JS-04 · OR-06 |
| **P0-09** | **Gate / unit-test coverage** | **New Build** | P0-02, P0-03, P0-04 | JobOps has **no unit tests at all** — `tests/` is 10 bash/curl scripts, none touching the scorer. A gate that silently mis-vetoes is worse than no gate, because it destroys exactly the trust P0 exists to create | Named cases pass: (a) hybrid/on-site ⇒ excluded pre-scoring even at maximal salary — the career doc's *"a high salary number should never be able to outbid this constraint"*; (b) the `Selenium` +4 / `Selenium UI` −12 contradiction; (c) each F4 unknown case; (d) a `<6`-month contract; (e) a ≥6-month contract at a product company | NO | JS-04 · OR-05 · F3/F4 |
| **P0-10** | **Per-candidate time instrumentation** | **New Build (trivial)** | P0-08 | The one measurement that makes every later phase transition falsifiable. Currently JobOps records **no** per-application time, so §1.4's tension between 25–30/day, the career doc's ~20/week, and the observed best day of 7 **cannot be settled by evidence**. It is also the input that selects P1 vs P2 | Time-to-decision and time-to-submit are recorded per candidate; a report yields median minutes/candidate and candidates/day over a ≥7-day window | NO | OR-09 · OR-10 |

### 4.2 P0 ingestion decision — the OR-08 fork

**The plan does not assume LinkedIn is permitted.** `COMPANY_RADAR_EXPERIMENT.md` §7 Channel E defers LinkedIn discovery *"indefinitely — verification-only role"*, and §3 states *"Not a LinkedIn scraper."* Whether that scopes the Radar experiment or JobOps as a whole is genuinely ambiguous and is **OR-08**.

#### Path A — LinkedIn via `ai-job-search/.agents/skills/linkedin-search` (preferred, if permitted)

| Aspect | Detail |
|---|---|
| Mechanism | `bun run …/cli.ts search --location "Bengaluru, Karnataka, India" --query <bucket> --jobage 7\|14 --remote remote --limit N --format json`; `detail <id>` for full description |
| Why it fits P0 | `--remote remote` is a **server-side filter that enforces the career doc's hard constraint at the source**, before a single candidate reaches the human. `detail` returns **`employment_type` and `seniority`** — the only structured inputs available anywhere for the ≥6-month contract rule (OR-07) and a seniority test |
| Integration | **Subprocess with a stdout-JSON boundary.** JobOps parses and owns everything downstream. **No file-based state model, no skill framework, no LaTeX toolchain, and no other part of `ai-job-search` is imported** (JS-R3) |
| Cost | Low–medium. New runtime dependency `bun`, not currently in `docker-compose.yml`; response-shape mapping into the candidate table |
| Constraint that must be honoured, not footnoted | The skill's own SKILL.md: *"⚠️ Personal use only — automated access is against LinkedIn's Terms of Service, so keep volume low."* This becomes a **rate limit and a volume cap in the design**, not a comment |
| Risk | V13: `ai-job-search` has never been run in this clone. The CLI is unit-tested upstream but **unproven here**. P0 must include one live smoke run before the gate is judged |

#### Path B — RemoteOK (fallback only)

| Aspect | Detail |
|---|---|
| Mechanism | Existing `scrapers/remoteok_integration.py`, re-run and re-pointed |
| Honest assessment | RemoteOK is a **global/US-centric remote board quoting USD**. It matches neither the Bengaluru targeting nor the ₹-denominated floor. Its realized yield to date is **zero applications from 77 rows** |
| What it still proves | It is a **live source that exercises the gate end-to-end**. For P0 — whose objective is a *trustworthy* queue, not a *large* one — that is sufficient to prove the mechanism, and it introduces no new dependency and no ToS question |
| What it cannot prove | Nothing about India-market yield, salary-rule behaviour in ₹, or the volume needed for OR-10 |

#### What changes if OR-08 rules LinkedIn prohibited

| Element | Change |
|---|---|
| **P0-06** | Path B. RemoteOK becomes the P0 source |
| **P0-01…P0-05, P0-07…P0-10** | **Unchanged.** The gate, unknown semantics, bridge repair, dedup, queue, tests and instrumentation are all source-agnostic. **P0 remains fully deliverable** |
| **P0 exit criteria** | The *"one source produces usable jobs"* criterion is met in mechanism but **explicitly annotated as not market-representative**. OR-10's throughput question stays unanswerable at P0 |
| **P1** | **Direct company / ATS ingestion (Greenhouse / Lever / Ashby) is promoted to the top of P1** and becomes the primary path to India-relevant volume. This is well-supported: it is already the **highest-yielding real source** (5 of 10 recorded applications), and `/scrape` Step 2 independently prefers employer careers postings because aggregators *"routinely drop the requisition ID and the grade or seniority level"* |
| **Naukri** | **Does NOT move.** Naukri is not a substitute for LinkedIn and is not promoted merely because LinkedIn is blocked. It stays behind reconnaissance (§7, JS-01) — `/add-portal` Step 2.4 mandates a **stop** if listings are login-gated, and `COMPANY_RADAR_EXPERIMENT.md` §2 names Naukri specifically as a source *"dominated by service/staffing-firm postings that don't match the target role profile"* |

**Recommendation:** rule OR-08 explicitly before P0 begins. If the answer is "Radar-scoped only", take Path A. If it is "JobOps-wide", take Path B and promote ATS ingestion into P1 — do **not** take Naukri.

### 4.3 What P0 explicitly does NOT include

Per instruction, and each with its reason:

| Excluded from P0 | Why |
|---|---|
| **Naukri** | No mechanism exists to adapt; login-gating untested; named in `COMPANY_RADAR_EXPERIMENT.md` §2 as the noise source; a second portal before the first proves throughput violates §9's hard rule → **P2, behind reconnaissance** |
| **Gmail / n8n status automation** | Parked with entry criteria → §8 |
| **CV generation** | Increases per-application cost; 7 submissions in one day were achieved without it → §9 |
| **Cover letters** | Same → §9 |
| **ATS PDF verification** | Quality control, not throughput; its precondition (a generated PDF) does not exist → §9 |
| **Calibration / fit-engine learning** | Outcome corpus is 10 applications, 1 resolved, 8 days old. Calibration here would be numerology → §9 |
| **Multi-agent orchestration** | `COMPANY_RADAR_EXPERIMENT.md` §3 *"Not a full multi-agent architecture on day one"*; a deterministic gate is auditable, an agent swarm is not → §9 |
| **Auto-submit** | **Permanently rejected** → §10, JS-R1 |
| Three-component fit model, explainable rank presentation, triage/deep tiering, portal health monitoring, second source | P1 → §6 |
| Company research cache, outcome detail, answer packs | P2 → §7 |

**Also not in P0, and worth naming explicitly:** P0 does **not** attempt to hit 25–30/day. P0 attempts to make the funnel *trustworthy and measured* so that the 25–30 question becomes answerable. Conflating the two is how P0 grows into P2.

---

## 5. P0 Exit Criteria

P0 → P1 only when **all eight** hold, each with named evidence. No criterion is satisfied by assertion.

| # | Criterion | Evidence that proves it |
|---|---|---|
| **X1** | **Policy rules are authoritative** | `docs/Career_Strategy_and_Search_Preferences.md` is committed and registered in `docs/INDEX.md`; the machine-readable ruleset is versioned; every rule cites a §-reference in the career doc; `resume_config.json`'s status is recorded (OR-01b) |
| **X2** | **Gate decisions are deterministic and tested** | Same posting + same ruleset version ⇒ byte-identical verdict across runs. The P0-09 named cases pass, including the career doc's own worked constraint: a maximal-salary hybrid role is **excluded pre-scoring** and never reaches the shortlist |
| **X3** | **UNKNOWN behaves correctly** | The F4 regression cases pass: empty experience, empty location, absent salary, absent employer type each yield `UNKNOWN`, contribute zero favourable signal, and are surfaced as unassessed. **No default-to-good path remains reachable** |
| **X4** | **One source produces usable jobs** | ≥1 live run under the OR-08-selected path yields candidates with enough JD text for a non-`UNKNOWN` **work-mode** verdict. If Path B, this criterion is annotated *"mechanism proven, market representativeness not proven"* |
| **X5** | **Discovery→queue→opportunity flows end-to-end** | A candidate traverses ingest → dedup → gate → queue → human decision → `opportunities`, with provenance queryable in both directions. F2 is closed |
| **X6** | **Dedup works** | Two consecutive ingestion runs add zero duplicates; a candidate already in `opportunities` is not re-queued; the key strategy is demonstrated against a synthetic second source |
| **X7** | **No critical data-loss path exists** | Migration procedure is governed (CONFLICT-2) and the applied set is derivable from the database; the career-policy artifact is committed (CONFLICT-9); the runtime-DB tracking question has an explicit ruling (CONFLICT-3) — *a decision to accept the risk counts, silence does not*; the write boundary has a ruling (CONFLICT-1) |
| **X8** | **Candidate-time measurement functions** | ≥7 days of per-candidate timing data; a report yields median minutes/candidate and candidates/day. **This is what makes OR-09/OR-10 answerable and P1-vs-P2 sequencing evidence-based rather than assumed** |

**Exit review is a document, not a feeling.** The P0 exit review should record each of X1–X8 with its evidence, state the measured baseline, and — critically — state **where candidate time actually went**. That measurement, not this plan, decides whether P1 (better ordering) or P2 (less friction per application) is the correct next phase.

---

## 6. P1 Backlog — Quality of Triage

**Entry:** P0 exit review completed with evidence for X1–X8.
**Objective:** make the human's *first five* candidates their *best five*, and add the second source.
**Non-objective:** more automation. P1 changes ordering and breadth, not who decides.

| Pri | Capability / task | Class | Dependency | Reason | Acceptance criterion | Owner decision? | JS / OR |
|---|---|---|---|---|---|---|---|
| **P1-01** | **Technical Fit** — extend skills + domain scoring; implement the declared-but-unread `keyword_synonyms`; justify or replace the hardcoded `max_possible_score` normalisers (100 and 50); add unit tests | **Extend** | P0 exit | Closest existing component to sound. `keyword_synonyms` is configuration fiction today — declared in `resume_config.json`, read by no code | Synonym expansion demonstrably changes matches on a fixture set; normalisers are documented or replaced; unit tests exist | NO | JS-05 |
| **P1-02** | **Preference / Career Fit** — scored **only over what is known**, carrying an explicit coverage/confidence term | **Extend** | P1-01; OR-03 | Must never present an unassessed job as a good fit. This is the scoring-side counterpart to P0-04's gate-side honesty | A candidate with unknown salary + unknown employer type is reported as **unassessed**, with its coverage stated — never as a high preference fit | **YES** — OR-03 | JS-05 · OR-03 |
| **P1-03** | **Opportunity Quality** — seeded with mass-posting detection | **New Build** *(adapting `/scrape` Step 2.5)* | P1-01 | The cheapest real signal available: ≥2 same-company/req postings differing only by city, computable from data ingestion already holds. Must be presented as *"a caution signal, not an accusation"* — never a fit downgrade, never a silent exclusion | Mass-posted clusters are consolidated to one row with the spread noted; no company is labelled fraudulent; fit score is unchanged by the signal | NO | JS-05 |
| **P1-04** | **Explainable rank reasons** — persist `strengths[]` / `gaps[]` **verbatim** | **Extend** *(adapting `/rank` Step 4)* | P1-01…P1-03 | *"Without them, nothing later can recover why a job did or didn't make the shortlist."* Never expand to prose, never reformat. Treat as untrusted data downstream | Every ranked candidate carries 1–3 verbatim strength and gap bullets, persisted and rendered | NO | JS-07 |
| **P1-05** | **Triage vs deep-evaluation separation** | **Adapt** *(`/rank` triage vs `/apply` Step 1 authoritative)* | P1-04 | Keeps the cheap pass cheap. Triage scores from posting text only — no company research, no external lookups — so it can run on every batch | Triage is demonstrably cheaper per candidate than deep evaluation; deep evaluation always re-runs and is never substituted by a triage score | NO | JS-08 |
| **P1-06** | **Funnel-state completion** — remaining stages from §11; plus a `drafted`-equivalent state and quiet-application follow-up derivation | **Extend** *(vocabulary from `/outcome`)* | P0-08; CONFLICT-7 | `drafted` is *"open but distinct — nothing was sent, so no follow-up is ever due"*, and deadline urgency still applies to it: *"documents written, never sent, and now unsendable"* is exactly the failure a scaling push creates. Days-quiet and follow-ups-sent are **derivable from fields JobOps already has** | All 13 measurement stages (§11) are representable; a drafted-but-unsent candidate with a passing deadline is surfaced | **YES** — CONFLICT-7 (new states in `opportunities` vs. upstream candidate table) | JS-10, JS-11 · CONFLICT-7 |
| **P1-07** | **Portal health monitoring** | **Adapt** *(`/scrape` Step 4.75)* | P1-08 | Addresses an **observed** failure: this system's only scraper went stale for **nine months** with nobody noticing (F1). Bounded by design — one sentinel probe, at most one retry; *"a 429 is never evidence of breakage"* | A deliberately broken parser is detected from a run's own output without extra fetches; a rate-limited portal reports `inconclusive`, never `broken` | NO | JS-09 |
| **P1-08** | **Direct company / ATS source ingestion** (Greenhouse / Lever / Ashby) | **New Build** | P0-07 (dedup must be load-bearing first) | **The highest-evidence source in the repository**: 5 of 10 recorded applications. Retains req ID and grade that aggregators drop. **Promoted to top of P1 if OR-08 blocks LinkedIn** (§4.2) | ≥1 ATS-backed careers source ingests end-to-end through the P0 gate; dedup holds across two genuinely different sources | NO | JS-02 |

**Architectural references only.** `/rank`'s triage model, PASS/FAIL/FLAG gate semantics, persisted strengths/gaps, the never-score-unfetched rule, and idempotent ranking are adopted as **design properties**. **`ai-job-search`'s file-based state model (`seen_jobs.json`, `job_search_tracker.csv`) is NOT imported** — JobOps keeps SQLite as its system of record (JS-R3).

**P1 → P2 exit criteria:**

- Ranking demonstrably improves review ordering — measured, e.g. the rank position of candidates the human actually chose to apply to, compared against P0's unranked ordering.
- Source quality is comparable — per-source yield, veto rate and unknown rate are reportable (§11).
- The candidate queue is stable — no dedup regressions, no gate non-determinism across two sources.
- **The actual time bottleneck is measurable** — P0-10 data plus P1 volume identifies where candidate time goes: reading, deciding, or completing forms. **This measurement, not assumption, scopes P2.**

---
## 7. P2 Backlog — Application-Friction Reduction

**Entry:** P0/P1 measurement has **established where candidate time is actually consumed.** P2 is the phase most at risk of building the wrong thing, because its central premise — that form completion is the binding cost — is currently **UNKNOWN**. If the P0-10/P1 data shows the bottleneck is elsewhere, **P2 is re-scoped or skipped.**

| Pri | Capability / task | Class | Dependency | Reason | Acceptance criterion | Owner decision? | JS / OR |
|---|---|---|---|---|---|---|---|
| **P2-01** | **Application-field collection** — record what each employer's form actually asks | **New Build (thin)** | P1 exit + time data confirming form cost | Per-employer field requirements are the true variable cost of a submission. Nothing records them today | Fields required per employer are captured and reusable across applications to the same employer | NO | JS-12 |
| **P2-02** | **Prepared answer packs** | **Adapt** *(`08-application-forms.md`)* | P2-01 | The highest throughput-per-unit-effort item in the whole `/apply` family, and — unlike CV generation — it targets time actually spent **at the form**. Plain `.txt` the candidate pastes; word/character counts **measured programmatically, not estimated**; short variants for tighter-than-expected limits; `NOTE TO SELF` blocks marked *not for pasting* | A pack exists per employer; every claim traces to committed profile sources; counts are measured; the candidate reports reduced typing time | NO | JS-12 |
| **P2-03** | **Application-ready information pack** — URL, deadline, gate verdict + evidence, prepared answers, CV to attach | **New Build** | P2-02 | Makes a reviewed candidate actionable in one place rather than reassembled per application | One view contains everything needed to complete a submission without re-deriving anything | NO | JS-13 |
| **P2-04** | **Factual grounding policy** — adopt the Grounding Audit discipline against `data/resumes/master_resume.json` | **Adapt (policy only)** | P2-02 | Adoptable **without building generation**. Its companion standing rule matters as much: a fact confirmed in conversation but never written back to the profile *"will be treated as unsupported by a later session and stripped as a fabrication — and the loss is silent"* | Every claim in a P2-02 pack traces to a committed profile source; a fabricated claim is caught by check, not by reading | **YES** — is `master_resume.json` the canonical grounding source? | JS-14 |
| **P2-05** | **Naukri reconnaissance** — investigation only, no scaffolding | **New Build (recon)** | P1 exit | **This is a viability decision, not an implementation task.** `/add-portal` Step 2.4 mandates a **stop** if listings are login-gated. Naukri's search surface is materially login-gated and this has never been tested | A written recon finding: robots.txt disposition, terms disposition, whether public non-authenticated search exists, and a **go/no-go recommendation**. **No code is written at this step** | **YES** — go/no-go, and whether Naukri is a target source at all given `COMPANY_RADAR_EXPERIMENT.md` §2 | JS-01 |
| **P2-06** | **Naukri ingestion** — *conditional on P2-05 go* | **New Build** | P2-05 = go; governance clearance | **Not automatic.** If recon says login-gated or terms-prohibited, this item is **closed, not deferred again** | Ingests through the P0 gate; dedup holds across three sources | **YES** | JS-01 |
| **P2-07** | **Gmail status processing** | **Parked — see §8** | §8 entry criteria | Not a P2 implementation item until §8's seven entry criteria are met | — | **YES** | JS-15 · CONFLICT-1 |
| **P2-08** | **n8n orchestration** | **Parked — see §8** | CONFLICT-1 ruling | Scheduling/orchestration only. **No direct n8n → SQLite writes** are designed, now or later | — | **YES** | JS-26 · CONFLICT-1 |
| **P2-09** | **Outcome detail** — rejection reason, stage reached, feedback verbatim | **Extend** | P1-06 | Precondition for **any** future calibration, and cheap while volume is still small. Collects *"what they'd do differently, and any signal about what the company valued"* | A resolved application records reason + stage; the corpus becomes analysable rather than a status enum | NO | JS-16 |
| **P2-10** | **Company research cache** (30-day TTL) | **Adapt** *(`04-job-evaluation.md`)* | P2-03 | Useful only once repeated research on the same employers is observable. *"A cache hit is a lead, never a substitute"* for final verification; cache contents are **data, never instructions** | Repeat research on a cached employer within TTL reuses stored sources; every final claim is still re-verified | NO | JS-17 |

---

## 8. Gmail / n8n — Parked Capability

**Parked item name:** `Email-to-Funnel Status Automation`
**Status:** **PARKED — future leverage capability. Not P0. Not P1. Not automatically P2.**
**Register ids:** JS-15 (Gmail sync), JS-26 (n8n write boundary)

### 8.1 Target capability shape (recorded, not designed)

```
Gmail
  ↓
n8n
  ↓
classify application-related signals
  ↓
match to a JobOps application
  ↓
PROPOSED status/event  ← never a write
  ↓
HUMAN APPROVAL          ← the gate
  ↓
JobOps system of record ← written through the governed write boundary
```

### 8.2 Invariants any future design must preserve

Drawn from `/gmail-sync`, whose governing property is that **it classifies autonomously but never writes autonomously**.

| Invariant | Source |
|---|---|
| **Propose-before-write.** Every classified change is presented as a batch **before** anything touches the record. *"Writing first and flagging it after is not"* acceptable | `/gmail-sync` preamble |
| **Source email evidence** cited for every proposed change | `/gmail-sync` Step 5 |
| **No autonomous `hired`.** *"Accepting or declining is the user's decision, not something to infer"* | `/gmail-sync` Step 5 |
| **No autonomous `offer_declined`** — same rule | `/gmail-sync` Step 5 |
| **Conflicts and unmatched signals surface for review**, never guessed | `/gmail-sync` Step 5 conflict rule |
| **JobOps remains the system of record** | `COMPANY_RADAR_EXPERIMENT.md` §12; this plan §12 |
| **Classification reads full message bodies, never snippets** — snippets truncate the phrase distinguishing *"we'd like to schedule a call"* from *"thanks for applying"* | `/gmail-sync` Step 4 |
| **NO direct n8n → SQLite writes.** n8n may orchestrate and propose; it may not write | CONFLICT-1; this plan §12 |

### 8.3 Entry criteria — all seven must hold

| # | Criterion | Currently |
|---|---|---|
| **E1** | P0 funnel states exist | ✗ — F5: four of eight stages unrepresentable |
| **E2** | P0/P1 ingestion is stable | ✗ — automated ingestion yields zero today (F1) |
| **E3** | Application volume is **materially higher than today** | ✗ — 10 applications total, best day 7 |
| **E4** | Manual email checking / status maintenance is **measured** as a meaningful candidate-time cost | ✗ — unmeasured; P0-10 is the instrument |
| **E5** | The write boundary has been **explicitly ruled** | ✗ — CONFLICT-1 open |
| **E6** | Gmail access/connector mechanism is **approved** | ✗ — no ruling; `Gmail` exists in JobOps only as a value in a **dropped** CHECK enum |
| **E7** | Status transitions can be represented **without ambiguity** | ✗ — transitions are unguarded, with no audit trail and no `status_changed_at` |

**Zero of seven are met.** This is why the item is parked rather than scheduled.

### 8.4 Exit criterion

> A **measurable reduction in manual status-maintenance time** without increasing incorrect status assignments.

Both halves are required. A time saving bought with wrong statuses corrupts the outcome corpus that P3/P4 calibration would later depend on — and per `/gmail-sync`, a wrong write *"silently corrupts application history."*

**Nothing about this workflow is designed or implemented now.**

---

## 9. P3 / P4 Backlog — Later Quality & Learning

**These optimize conversion quality, not discovery throughput. That is precisely why they must not be front-loaded.**

The distinction is load-bearing and worth stating plainly: a better CV does not increase how many opportunities reach the human or how many applications can be completed per hour — it **increases the cost of each one** while improving the chance each converts. Front-loading conversion work before throughput work means paying that cost across a pipeline that is not yet delivering candidates at all (F1). The repository already demonstrates the point: **7 applications were submitted in a single day with no document generation of any kind** (V11).

Conversion work becomes the right investment when the evidence says the problem is *response rate*, not *volume*. Today there is no such evidence: the outcome corpus is **10 applications, 1 resolved, 8 days old** (V12).

| Pri | Capability / task | Class | Dependency | Reason deferred | Owner decision? | JS |
|---|---|---|---|---|---|---|
| **P3-01** | CV tailoring | **Deferred** | Sustained volume + evidence of a conversion problem | Increases per-application cost; the `/apply` workflow costs a posting fetch, a research agent, two LaTeX compiles, ≥2 PDF visual reads and an iterate-to-2-pages loop **per application** — structurally the opposite of a throughput mechanism | **YES** — is document generation wanted in JobOps at all, or does it stay external? | JS-18 |
| **P3-02** | Cover letters | **Deferred** | P3-01 | Same | **YES** | JS-18 |
| **P3-03** | Drafter / reviewer workflow | **Deferred** | P3-01 | Same; also introduces agent orchestration deferred by `COMPANY_RADAR_EXPERIMENT.md` §3 | NO | JS-18, JS-22 |
| **P3-04** | ATS PDF verification | **Deferred** | P3-01 shipped **and** response rate identified as the problem | Quality control, not throughput. **Its precondition — a generated PDF — does not exist.** `tools/verify_pdf.py` is ~60 lines over `pypdf` + `pdftotext` and remains adaptable at any time, so deferring costs nothing unrecoverable | NO | JS-19 |
| **P4-01** | Fit-engine calibration | **Deferred** | P2-09; score-at-decision immutability; a large enough resolved-outcome corpus | Calibration on 10 applications and 1 resolved outcome would be **numerology**. Requires: provenance to the score **at decision time**, immutability of that score against later ruleset changes, resolved labels with reasons, and **the predictive question stated in advance** — otherwise it becomes retrospective story-fitting. `migrations/004_add_parliament_decisions.sql` already anticipated this shape (`applied`/`callback`/`interview`/`offer`) and **was never applied** | **YES** — required sample size; disposition of unapplied `004` | JS-20, JS-28 |
| **P4-02** | Outcome-based model improvement | **Deferred** | P4-01 | Downstream of calibration existing at all | NO | JS-20 |
| **P4-03** | Multi-agent orchestration | **Deferred** | Every earlier phase proving value | `COMPANY_RADAR_EXPERIMENT.md` §3 *"Not a full multi-agent architecture on day one"*; §9's hard rule. **A deterministic gate is auditable; an agent swarm is not** — and P0's entire value is auditability | NO | JS-22 |

---

## 10. Permanently Rejected Items

**Recorded so the reasoning is not reconstructed later. Not backlogged. Not revisited on a trigger.**

| id | Item | Grounds |
|---|---|---|
| **JS-R1** | **Automatic application submission** | Strategic objective: *"Final application submission remains HUMAN-GATED permanently."* `COMPANY_RADAR_EXPERIMENT.md` §3 *"Not a mass-application bot"*; §10 defers *"Mass Easy Apply automation"* and *"Fully autonomous applications."* And `ai-job-search` — the reference implementation — **contains no submission mechanism at all**: `/apply` stops at drafts. **Not proposed, not designed, not scaffolded.** Any future proposal containing it is to be rejected on these grounds |
| **JS-R2** | **Automated recruiter outreach / DM automation** | `COMPANY_RADAR_EXPERIMENT.md` §3: *"Not an automated outreach/DM system on any channel… All outbound messages are human-drafted-or-approved and human-sent throughout every phase, including later automated phases."* `/scrape` Step 4.5 generates **search links only**; its Rule 7 forbids programmatic people lookups |
| **JS-R3** | **Wholesale `ai-job-search` replacement / fork** | Its file-based state model, skill framework and LaTeX toolchain are structurally incompatible with JobOps' SQLite system of record. **Only individual mechanisms are adapted**, each named explicitly in §4, §6, §7 and §12 |
| **JS-R4** | **Job-search backend logic inside `ai-quality-engineering`** | `ai-quality-engineering/docs/architecture.md` §5 names JobOps SQLite **read-only** to that repository; `COMPANY_RADAR_EXPERIMENT.md` §12 restates *"read-only, non-destructive… no writes back."* Its `1B-07` is about *exercising a retrieval stage against* JobOps data, not producing it. The career document §5.1 independently confirms the direction of the dependency: the evaluation suite *"uses… the JobOps SQLite database as its evaluation corpus"* |
| **JS-R5** | **Converting hard vetoes into ordinary weighted scoring** | The career document forbids it in its own words: *"Do not collapse this into a scoring dimension. A high salary number should never be able to outbid this constraint algorithmically."* This is also **the exact defect F3 documents in the current implementation** (max −5.0 points), which is why P0-02 is a new build rather than an extension of `simple_scorer.py` |

---

## 11. Measurement / KPI Framework

**Purpose:** make phase transitions evidence-based. Every number below is either measurable at P0 or explicitly marked as not-yet-measurable.

**No target values are asserted.** The repository supports **10 applications total** and a **best recorded single day of 7**. The *"~15/day"* figure is treated throughout as an **OWNER-DEFINED OPERATIONAL BASELINE, not a measured fact**, pending OR-09. The career document's own §5 cadence — *"apply to ~20 companies"* in a week — is recorded as a third, conflicting figure (§1.4).

### 11.1 Funnel stages

| # | Stage | Representable today? | Introduced by |
|---|---|---|---|
| 1 | **discovered** | Partial — `scraped_jobs`, RemoteOK only, stale | P0-06 |
| 2 | **deduplicated** | ✗ — within-source only; **no index on `opportunities`** | P0-07 |
| 3 | **JD acquired** | ✗ — `description` exists but is truncated to 2000 chars and never quality-checked | P0-06 |
| 4 | **policy PASS** | ✗ — no gate exists | P0-02 |
| 5 | **policy FAIL** | ✗ — structurally impossible (F3) | P0-02 |
| 6 | **policy UNKNOWN** | ✗ — and currently **inverted** (F4) | P0-03/P0-04 |
| 7 | **relevant** | Proxy only — `match_score` / `classification`, RemoteOK only | P1-01…P1-03 |
| 8 | **human reviewed** | ✗ — implicit in the human's head | P0-08 + P0-10 |
| 9 | **application submitted** | ✅ — `status='Applied'` + `applied_date` | exists |
| 10 | **acknowledged** | ✗ — no field; `interactions` could carry it but has 3 seed rows | P1-06 |
| 11 | **shortlisted** | Partial — `status='Screening'` is the nearest analogue | P1-06 |
| 12 | **interview** | ✅ — `status` Technical/Manager; `interactions.type='Interview'` | exists |
| 13 | **offer** | ✅ — `status='Offer'`; `offer_date` | exists |

**Six of thirteen stages are unrepresentable today, and one is inverted.** That is the measurement gap P0 closes.

### 11.2 Rate and volume metrics

| Metric | Definition | Measurable at | Note |
|---|---|---|---|
| **Candidate time per stage** | Minutes spent by the human, per funnel stage | **P0** (P0-10) | **The most important metric in this plan.** It is the denominator of the optimization target and it selects P1 vs P2 |
| **Jobs processed per day** | Stage 1 → stage 6 throughput | **P0** | System-side; not candidate-limited |
| **Qualified jobs per day** | Stage 4 (`policy PASS`) per day | **P0** | The number P0 exists to make real and trustworthy |
| **Applications per day** | Stage 9 per day | Exists | Current: 10 total, best day 7 |
| **Application → acknowledgement rate** | 10 ÷ 9 | **P1-06** | Needs stage 10 to exist |
| **Acknowledgement → shortlist rate** | 11 ÷ 10 | **P1-06** | |
| **Shortlist → interview rate** | 12 ÷ 11 | **P1-06** | |
| **Source-level yield** | Per source: discovered → PASS → submitted → acknowledged | **P0** (one source) / **P1** (comparative) | Requires provenance to survive the import bridge (P0-05) |
| **Veto rate** | Stage 5 ÷ stage 2, **broken down by rule id** | **P0** | Per-rule breakdown is what makes a mis-specified rule visible instead of silently shrinking the queue |
| **Unknown rate** | Stage 6 ÷ stage 2, **by field** (salary / work mode / employer type / duration) | **P0** | Expected to be high for salary in Indian postings — which is exactly why OR-03(c) matters |
| **JD acquisition success rate** | Stage 3 ÷ stage 2 | **P0** | A low rate means the gate is reasoning from thin text and unknown rates are inflated for the wrong reason |

### 11.3 Measurement integrity rules

1. **Never claim a target value the evidence does not support.** Where a number is owner-defined rather than measured, label it so.
2. **Veto rate must be reported per rule id**, never only in aggregate — an over-broad rule and a correctly-strict market look identical in the aggregate.
3. **Unknown rate must be reported per field.** A single blended "unknown %" hides which policy question is actually unanswerable from the source.
4. **A stage that cannot be measured is reported as unmeasured**, never as zero.
5. **Score-at-decision is immutable.** Once a candidate is reviewed, the verdict and score it carried are frozen against later ruleset changes — otherwise every P4 calibration measures the current ruleset against a rewritten past.

---

## 12. Architecture Boundaries

| Boundary | Rule | Authority | Status |
|---|---|---|---|
| **System of record** | JobOps SQLite is the single system of record for opportunities, applications and outcomes | `COMPANY_RADAR_EXPERIMENT.md` §12; career doc §5.1 | Verified |
| **Write ownership** | **Proposed:** the REST API is the sole writer to `data/jobs-tracker.db`. n8n may read and may propose; it may **not** write | — | **CONFLICT-1 — OWNER RULING REQUIRED** |
| **Gate position** | The policy gate runs **before** scoring. A `FAIL` excludes without a score being computed | **Career doc §4**: *"filtered out at the same pre-scoring veto stage"*, *"Do not collapse this into a scoring dimension"* | **Ruled by the career document** |
| **Veto vs weight** | No hard veto may be expressed as a weighted term | Career doc §4; JS-R5; F3 | **Ruled** |
| **Candidate vs opportunity** | **Proposed:** candidates live upstream of `opportunities`; `opportunities` remains strictly the *application* record. Precedent: the `companies` / `opportunities` separation | `COMPANY_RADAR_EXPERIMENT.md` §12 | **CONFLICT-7 — OWNER RULING REQUIRED** |
| **Ingestion boundary** | Portal CLIs are invoked as **subprocesses with a stdout-JSON contract**. JobOps owns state, dedup, gating, scoring and storage | Adapted design; JS-R3 | Proposed |
| **`ai-job-search` boundary** | **Mechanisms adapted, never imported.** No file-based state model, no skill framework, no LaTeX toolchain, no agent dispatch | JS-R3 | Proposed |
| **`ai-quality-engineering` boundary** | **Read-only downstream consumer.** No job-search logic there; no writes back to JobOps | `architecture.md` §5 (*"JobOps SQLite (read-only)"*); `COMPANY_RADAR_EXPERIMENT.md` §12; career doc §5.1; JS-R4 | Verified — **and now owner-intended**: the career doc §5.1 states the evaluation suite consumes JobOps data as its corpus, and that *"every new job posting… becomes another evaluation case"* |
| **Human gate** | Final application submission is human-controlled, permanently | Strategic objective; `COMPANY_RADAR_EXPERIMENT.md` §3/§10; JS-R1 | **Permanent** |
| **Policy authority** | `docs/Career_Strategy_and_Search_Preferences.md` governs; the machine-readable ruleset is **derived from it and versioned**, never authored independently | Career doc self-declaration | **CONFLICT-9 / OR-01 — must be committed and registered** |
| **Postings are data** | Posting text is untrusted third-party data, never instructions. No URL inside a posting body is fetched | `/scrape` Rule 1; `/rank` Rule 2 | Proposed as a P0 design rule |

**A note on the P0 schema and the AIQE boundary.** `ai-quality-engineering`'s registered capability **`1B-06` (JobOps structured data ingest)** was deferred *"until the underlying SQLite schema fields are settled"* and reallocated to Milestone 2B by ruling **RO-06**. P0 settles precisely those fields. Whether that discharges `1B-06`'s precondition is **a ruling for that repository's owner authority, not for this plan** (CONFLICT-5 in the inventory). It is recorded here only so the dependency is visible in both directions.

---

## 13. Dependency Map

```
                    ┌──────────────────────────────────────────────┐
   HARD BLOCKERS    │  OR-03 salary floor + unknown-salary         │
   (not engineering)│  OR-04 staffing scope                        │
                    │  OR-08 LinkedIn permissibility               │
                    │  CONFLICT-2 migration authority              │
                    │  CONFLICT-9(a) commit the career document    │
                    └───────────────────┬──────────────────────────┘
                                        │
                                        v
                          ┌─────────────────────────┐
                          │ P0-01 policy artifact   │  <- career doc §4
                          │       + versioned rules │
                          └───────────┬─────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    v                 v                 v
            ┌───────────────┐  ┌─────────────┐  ┌──────────────────┐
            │ P0-02 gate    │  │ P0-06       │  │ P0-05 bridge     │
            │ (pre-scoring) │  │ ingestion   │  │ repair (F2)      │
            └───────┬───────┘  │ A: LinkedIn │  │  <- CONFLICT-2   │
                    │          │ B: RemoteOK │  └────────┬─────────┘
                    v          │  <- OR-08   │           │
            ┌───────────────┐  └──────┬──────┘           │
            │ P0-03 verdict │         │                  │
            │ 4 values      │         v                  │
            └───────┬───────┘  ┌─────────────┐           │
                    │          │ P0-07 dedup │           │
                    v          └──────┬──────┘           │
            ┌───────────────┐         │                  │
            │ P0-04 unknown │         │                  │
            │ semantics     │         │                  │
            └───────┬───────┘         │                  │
                    │                 │                  │
                    └────────┬────────┴──────────────────┘
                             v
                    ┌─────────────────┐      ┌──────────────────┐
                    │ P0-08 queue     │─────>│ P0-10 time       │
                    │ 3 lanes         │      │ instrumentation  │
                    └────────┬────────┘      └────────┬─────────┘
                             │                        │
                    ┌────────┴────────┐               │
                    │ P0-09 tests     │               │
                    └────────┬────────┘               │
                             │                        │
                             v                        v
                    ╔════════════════════════════════════════╗
                    ║  P0 EXIT REVIEW  (X1..X8, evidenced)   ║
                    ║  -> measures WHERE candidate time went ║
                    ╚════════════════┬═══════════════════════╝
                                     │
                   ┌─────────────────┴─────────────────┐
                   │  the measurement decides the fork  │
                   v                                   v
        ┌─────────────────────┐              ┌─────────────────────┐
        │ P1 triage quality   │              │ P2 friction         │
        │ (too much to read)  │              │ (each one costs     │
        │ P1-01..P1-08        │              │  too much)          │
        └──────────┬──────────┘              │ P2-01..P2-10        │
                   │                          └──────────┬─────────┘
                   └──────────────┬──────────────────────┘
                                  v
                       ┌──────────────────────┐
                       │ Gmail/n8n PARKED     │  <- E1..E7 (0/7 met)
                       │ JS-15, JS-26         │     CONFLICT-1
                       └──────────┬───────────┘
                                  v
                       ┌──────────────────────┐
                       │ P3/P4 conversion     │  <- needs a large
                       │ quality + learning   │     resolved-outcome
                       └──────────────────────┘     corpus
```

**Critical path:** `OR-03 + OR-04 + CONFLICT-9(a)` → `P0-01` → `P0-02` → `P0-03` → `P0-04` → `P0-09`.
**Parallel path:** `OR-08` → `P0-06` → `P0-07`; and `CONFLICT-2` → `P0-05`.
**Convergence:** `P0-08` + `P0-10` → exit review.

**Note the shape:** the longest pole is not engineering. It is four owner rulings.

---

## 14. Deferred Items / Backlog Traceability (JS-01 … JS-29)

Every identifier from `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` §11, mapped to this plan. **Nothing is silently dropped.** Per the `ai-quality-engineering` register's §1.3 discipline, *a capability is never deleted* — items whose status changes are re-stated in place with the reason.

| JS id | Item | Inventory phase | **Plan disposition** | Change since inventory |
|---|---|---|---|---|
| **JS-01** | Naukri ingestion | P2 | **P2-05 recon (owner go/no-go) → P2-06 conditional.** Explicitly **not** promoted if OR-08 blocks LinkedIn | Split into recon + conditional build |
| **JS-02** | Company careers / ATS ingestion | P1 | **P1-08.** **Promoted to top of P1 if OR-08 blocks LinkedIn** | Conditional promotion |
| **JS-03** | Wellfound / Indeed ingestion | Unallocated | **Unallocated.** No mechanism in either repository; value unproven | — |
| **JS-04** | *(referenced in inventory dependencies as "the gate"; had no deferral row because it is P0)* | P0 | **P0-01 … P0-05, P0-08, P0-09** — the core of P0 | Now decomposed into named tasks |
| **JS-05** | Three-component fit model | P1 | **P1-01, P1-02, P1-03** | Decomposed |
| **JS-06** | *(referenced as dedup; no deferral row — P0)* | P0 | **P0-07** | Now named |
| **JS-07** | Explainable "why recommended" | P1 | **P1-04** | — |
| **JS-08** | Triage vs deep-evaluation tiering | P1 | **P1-05** | — |
| **JS-09** | Portal health monitoring | P1 | **P1-07** | — |
| **JS-10** | Funnel state model completion | P0 partial / P1 | **P0-03/P0-08 (partial), P1-06 (remainder).** Still gated on **CONFLICT-7** | — |
| **JS-11** | `drafted` state + quiet follow-up | P1 | **P1-06** | Merged with JS-10 |
| **JS-12** | Application-field collection + answer packs | P2 | **P2-01, P2-02.** **Conditional:** if P0-10 does not confirm form completion as binding, this is **re-scoped or dropped** | Condition made explicit |
| **JS-13** | Application-ready info pack | P2 | **P2-03** | — |
| **JS-14** | Factual Grounding Audit as policy | P2 | **P2-04** | — |
| **JS-15** | Email → status sync | P2 | **PARKED → §8.** Not a P2 implementation item; 0 of 7 entry criteria met | **Reclassified P2 → parked** |
| **JS-16** | Outcome / rejection detail | P2 | **P2-09** | — |
| **JS-17** | Company research cache | P2 | **P2-10** | — |
| **JS-18** | CV tailoring / cover letters | P3 | **P3-01, P3-02, P3-03** | — |
| **JS-19** | ATS PDF verification | P3 | **P3-04** | — |
| **JS-20** | Fit-engine calibration | P3 | **P4-01, P4-02** | Moved P3 → P4 to separate document quality from learning loop |
| **JS-21** | Company Radar advancement | Governed elsewhere | **Governed elsewhere — unchanged.** `COMPANY_RADAR_EXPERIMENT.md` §9 exit gate unmet; Phase 1 paused. **Nothing in this plan advances it** | — |
| **JS-22** | Multi-agent orchestration | P3+ | **P4-03** | — |
| **JS-23** | API authentication | Unallocated | **Unallocated — flagged. CONFLICT-8.** Decide explicitly rather than by omission before P0 | — |
| **JS-24** | Migration runner + history table | Unallocated | **P0 PREREQUISITE (recommended).** **CONFLICT-2 is a hard blocker** and JS-24 is the natural way to discharge it | **Elevated: unallocated → P0 prerequisite candidate** |
| **JS-25** | Untrack runtime SQLite DB | Unallocated | **Strongly advised before P0. CONFLICT-3.** Note the WAL-checkpoint modification now present in the working tree — **do not "clean" it with `git checkout`**, which would discard WAL-resident transactions | **Evidence strengthened** |
| **JS-26** | Retire / rewrite n8n workflow 06 direct write | Unallocated | **CONFLICT-1 ruling → then P2-08.** P0 must not add a third write path | — |
| **JS-27** | Remove or wire `prompts/` | Unallocated | **Unallocated.** Now clearly stale: `prompts/job_analysis.txt` describes a "QA Lead / ETL Testing Specialist" profile that the career document's four buckets supersede. Read by no code | **Staleness now confirmed by the career document** |
| **JS-28** | Disposition of unapplied migration `004` | Unallocated | **Unallocated → surfaces at P4-01.** Its schema anticipates the calibration shape | — |
| **JS-29** | **Align `data/resume_config.json` with the authoritative compensation policy.** The file currently carries the older ₹18L configuration — `profile.min_salary_inr: 1800000` and `filters.preferred_salary_range.min_inr: 1800000`. Repository Owner ruling **OR-03a** (2026-08-28) establishes **₹20 LPA** as the compensation veto threshold, so this executable configuration is **stale relative to current career policy** | — (new) | **Deferred to P0 implementation / configuration-alignment work (P0-01).** Not actionable during a ruling session. **The stale value has no policy force:** until that implementation work is explicitly authorized, `docs/Career_Strategy_and_Search_Preferences.md` and `OWNER_RULINGS_LOG.md` are the policy authority, and this JSON does not override them | **NEW — opened 2026-08-28 by Repository Owner ruling OR-03a** |
| **JS-R1…JS-R5** | Rejected items | Rejected | **§10 — permanently rejected, unchanged** | — |

**New items introduced by this plan:**

| id | Item | Where |
|---|---|---|
| **CONFLICT-9** | Career-policy artifact untracked and unregistered; cites a nonexistent `AI_QA_Learning_Roadmap_Scope.md` | §3.2 |
| **P0-10** | Per-candidate time instrumentation | §4.1 — the measurement that makes phase transitions falsifiable |
| **P2-05** | Naukri **reconnaissance** as a distinct, owner-decided gate before any Naukri build | §7 |

---

## 15. Explicit — What We Are NOT Building Now

| Not building | Phase | Why not now |
|---|---|---|
| **Automatic application submission** | **NEVER** | Permanently rejected. JS-R1 |
| **Automated recruiter outreach / DMs** | **NEVER** | Permanently rejected. JS-R2 |
| **Direct n8n → SQLite writes** | **NEVER** | Not designed now or later. Any Gmail capability proposes; the API writes. §8, §12 |
| **A fork of `ai-job-search`** | **NEVER** | Mechanisms adapted, never imported. JS-R3 |
| **Job-search logic in `ai-quality-engineering`** | **NEVER** | Read-only consumer. JS-R4 |
| **Any hard veto expressed as a weighted score** | **NEVER** | The career document forbids it in its own words. JS-R5 |
| Naukri ingestion | P2, conditional | No mechanism to adapt; login-gating untested; **not a substitute if LinkedIn is blocked** |
| Gmail / n8n status automation | Parked | 0 of 7 entry criteria met |
| CV tailoring, cover letters, drafter/reviewer | P3 | Optimize **conversion**, not throughput; raise per-application cost |
| ATS PDF verification | P3 | Quality control; precondition (a PDF pipeline) does not exist |
| Fit-engine calibration | P4 | 10 applications, 1 resolved. Would be numerology |
| Multi-agent orchestration | P4 | A deterministic gate is auditable; an agent swarm is not |
| Three-component fit model, explainable ranking, portal health, second source | P1 | P0 proves *trust*; P1 improves *ordering*. Conflating them is how P0 becomes P2 |
| Company Radar advancement | Governed elsewhere | Phase 1 exit gate unmet and paused |
| **Hitting 25–30/day** | Not a P0 goal | P0 makes the funnel trustworthy and **measured**, so the 25–30 question becomes answerable. OR-10 is still open |

---

## 16. Next Immediate Actions for the Repository Owner

**Ordered. Nothing in §4 begins until items 1–5 are answered.**

| # | Action | Type | Unblocks | Effort |
|---|---|---|---|---|
| **1** | **Commit `docs/Career_Strategy_and_Search_Preferences.md`** and register it in `docs/INDEX.md`. It is currently untracked with no git history and referenced by no governance document | Repository action | Everything — it is the authority P0 derives from | Minutes |
| **2** | **Rule OR-03.** (a) Is the veto threshold **₹18L** (the document's exception line) or **₹20L** (the task prompt's floor)? The ₹18–20L band is currently unclassified by both. (b) Confirm *"salary UNKNOWN is never PASS."* (c) Is unknown-salary **`UNKNOWN`** (queue and surface) or **`FAIL`** (exclude)? Most Indian postings state no salary, so (c) largely determines P0 queue volume | Ruling | P0-01, P0-02, P0-04 | — |
| **3** | **Rule OR-04.** The career document hard-excludes staffing firms **only inside the contract clause**, while calling staff augmentation *"Lower priority"* under Company Type. **Is a full-time role at a services/staffing firm `FAIL`, or a low-scoring `PASS`?** | Ruling | P0-01, P0-02 | — |
| **4** | **Rule OR-08.** Does `COMPANY_RADAR_EXPERIMENT.md` §7 Channel E bar LinkedIn **ingestion in JobOps generally**, or scope only the Company Radar experiment? **This selects P0's ingestion path** (§4.2) | Ruling | P0-06 | — |
| **5** | **Rule CONFLICT-2.** Who may apply a migration and by what procedure? Is applying `005` authorized to repair F2? Is a migration runner + history table (JS-24) a P0 prerequisite? | Ruling | P0-05, and all P0 schema | — |
| **6** | **Rule CONFLICT-1** — is the REST API the sole writer to `data/jobs-tracker.db`? | Ruling | P0 write design; prevents a third write path | — |
| **7** | **Decide CONFLICT-3** — untrack the runtime DB? **Do not resolve the current ` M data/jobs-tracker.db` with `git checkout`** — that would discard transactions that lived only in the WAL. A decision to accept the risk counts; silence does not | Ruling | X7 | — |
| **8** | **Decide CONFLICT-8** — API authentication before P0, or accepted as localhost-only with the n8n credential rotated? | Ruling | X7 | — |
| **9** | **Confirm OR-01(b)** — is `data/resume_config.json` regenerated from the career document, retired, or demoted to scoring-only input? It currently contradicts the document on both salary and role family | Ruling | P0-01 | — |
| **10** | **Clarify OR-02** — are the four search buckets **also an eligibility gate**, or **only query seeds**? | Ruling | P0 query design; not P0-blocking | — |
| **11** | **Define OR-09 and OR-10** — what did *"~15/day"* count, and is the 25–30 target **submitted/day** or **surfaced-for-review/day**? Note the three conflicting figures in §1.4 | Ruling | Every throughput claim; P2 sizing | — |
| **12** | *Optional:* supply or formally record the missing **`AI_QA_Learning_Roadmap_Scope.md`**, cited as a baseline by the career document §5 and §5.1 but present nowhere. Same class as `ai-quality-engineering` register **NA-06** | Repository action | Governance hygiene | — |
| **13** | *Optional:* supply the planning discussion **`Pasted markdown(20260828-140604).md`**, named as an input but not present on the filesystem. **No direction from it is incorporated into this plan** | Input | Completeness of this plan's inputs | — |

**Recommended sequencing:** do **1** immediately — it costs minutes and protects the authority everything else depends on. Then answer **2, 3, 4, 5** together in one sitting; they are the four hard P0 blockers and they are all policy questions, not engineering questions. **6, 7, 8** can follow within P0 planning. **10, 11** can trail into P0 execution without blocking it.

---

## Appendix A — Evidence Sources

| Source | Used for |
|---|---|
| `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` | Findings F1–F5; verified state V1–V15; JS-01…JS-28; CONFLICT-1…CONFLICT-8 |
| `docs/Career_Strategy_and_Search_Preferences.md` §1–§5.1, §8 | §2.2 policy table; OR-01…OR-07 status; §12 gate-position and veto-vs-weight rulings; §1.4 cadence conflict |
| `docs/COMPANY_RADAR_EXPERIMENT.md` §2, §3, §7, §9, §10, §12 | OR-08 / CONFLICT-4; JS-R1, JS-R2; JS-21; §12 boundaries |
| `docs/reports/migration-architecural-audit.md` | CONFLICT-2, CONFLICT-3; V6 |
| `docs/INDEX.md` | CONFLICT-9 (career doc unregistered) |
| `scrapers/simple_scorer.py`, `scrapers/remoteok_integration.py` | F3, F4; Path B assessment |
| `api-server.py`, `workflows/06-opportunity-manager-bash.json` | F2, CONFLICT-1, V7 |
| `data/resume_config.json` | OR-01(b) contradiction with the career document |
| `ai-quality-engineering/docs/PROJECT_ORIENTATION.md` §6, `docs/DEFERRED_ITEMS_REGISTER.md` §1.3, §8 NA-06 | Governance discipline; register style; dangling-citation precedent |
| `ai-job-search` — `linkedin-search/SKILL.md`, `job-scraper/SKILL.md`, `rank.md`, `04-job-evaluation.md`, `08-application-forms.md`, `outcome.md`, `gmail-sync.md`, `add-portal.md` | Architectural references throughout; §8 invariants |
| `git status`, `git log`, `grep` over `docs/`, `find ~` | Δ1, Δ2, Δ3; CONFLICT-9; missing-input verification |

---

## STATUS

**PLAN ONLY — AWAITING OWNER RULING**

No source code, SQLite schema, migration, workflow, configuration, dashboard code, prompt, or governance document was created or modified in producing this plan. No branch was created, no commit was made, no migration was applied, no database was changed, no issue was created. The only file written is this one.

**P0 does not begin until items 1–5 of §16 are answered.**
