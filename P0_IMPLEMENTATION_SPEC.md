# P0_IMPLEMENTATION_SPEC.md

**Type:** Implementation specification — **SPECIFICATION ONLY. NO CODE. NOT AN IMPLEMENTATION SESSION.**
**Repository:** `~/projects/jobs-application-automation` (JobOps)
**Written:** 2026-08-28
**HEAD:** `bf22ca1` — *docs(governance): register Career Strategy as authoritative career policy*
**Authority:** `OWNER_RULINGS_LOG.md` — 5 of 5 ruled, complete 2026-08-28
**Status:** Ready for a separate, explicitly-authorized P0 implementation session.

> **Nothing in this document was executed.** No source code, scoring logic, ingestion code, schema, migration, workflow, or configuration was created or modified in producing it. Migration 005 was **authorized but not applied** at the time of writing; it was subsequently applied on 2026-08-29 by a separately authorized session — see §10.3 and `P0_EXIT_REVIEW.md` §1.

---

## 1. Scope and Authority

### 1.1 What this specification is

An implementation-ready description of P0 — the **trustworthy, measurable, preference-gated candidate funnel** — grounded in verified repository state and in the five Repository Owner rulings recorded on 2026-08-28.

It contains no code. It defines behaviour, contracts, evidence semantics, acceptance tests, sequencing and exit criteria, so that a subsequent implementation session has no need to infer policy.

### 1.2 Authoritative inputs

| Document | Role |
|---|---|
| `docs/Career_Strategy_and_Search_Preferences.md` | **Canonical career policy.** Committed at `bf22ca1`. Not modified. |
| `OWNER_RULINGS_LOG.md` | **Ruling authority.** 5 of 5 closed. Supersedes stale configuration. |
| `JOBOPS_SCALING_EXECUTION_PLAN.md` | Phase structure, P0-01…P0-10, JS-nn backlog, CONFLICT-1…CONFLICT-9 |
| `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` | Verified evidence base, findings F1–F5 |
| `docs/reports/migration-architecural-audit.md` | Migration-system state |
| `docs/COMPANY_RADAR_EXPERIMENT.md` | Governance boundaries; source of OR-08's question |
| Live repository — `api-server.py`, `scrapers/`, `dashboard/`, `migrations/`, `data/jobs-tracker.db` | Current architecture |

### 1.3 Rulings in force

| id | Ruling, in force |
|---|---|
| **OR-03a** | ₹20 LPA is the compensation veto threshold. ₹20–30+ LPA is the target band. Supersedes the ₹18L in `data/resume_config.json`, which is stale configuration. |
| **OR-03b** | Salary not stated → **UNKNOWN**. Kept in queue, surfaced for human review. Never satisfies the ₹20 LPA floor. Never auto-shortlisted above a confirmed qualifying salary. Owner reviews escalations. |
| **OR-04** | Eligible for scoring = **remote AND ≥ ₹20 LPA**. Hybrid and on-site are vetoed pre-scoring. **Services/staffing/company type is NOT a separate hard veto** and does not exclude pre-scoring; it may influence scoring downstream. |
| **OR-08** | Radar-scoped only. P0 takes **Path A** — LinkedIn ingestion via the `linkedin-search` CLI, honouring its personal-use / low-volume notice as a designed rate limit. |
| **CONFLICT-2** | Repository Owner is the migration authority; no standing permission for autonomous execution. **Migration 005 authorized** as a scoped one-time migration. **JS-24** (runner + history table) governs future migrations. **Migration 004 remains unauthorized.** |

### 1.4 What P0 is not optimizing for

Per the strategic objective: **quality-adjusted opportunities per unit of candidate time** — not raw job count, not automation percentage, not application volume.

**P0 does not target 25–30/day.** It makes the funnel trustworthy and instrumented so that the 25–30 question becomes answerable. OR-09 (what the "~15/day" baseline counted) and OR-10 (whether 25–30 means *surfaced* or *submitted*) remain **open** (§18).

---

## 2. P0 Architecture

### 2.1 The pipeline

```
DISCOVERY            LinkedIn CLI adapter (Path A). Rate-limited, provenance-tagged.
     |               Produces RAW SOURCE RECORDS. No policy logic.
     v
NORMALIZATION        Raw record -> canonical candidate fields.
     |               Lossless: raw payload retained alongside.
     v
EVIDENCE EXTRACTION  Locate and classify work-mode and compensation evidence.
     |               Emits typed evidence with source + span + timestamp.
     |               NEVER infers a value it did not find.
     v
HARD POLICY GATE     Deterministic. Reads a versioned ruleset. No scoring input.
     |               Cannot be influenced by, and cannot consult, any score.
     v
PASS / UNKNOWN / FAIL
     |
     +-- FAIL     -> excluded from scoring. Retained with reason codes + evidence.
     +-- UNKNOWN  -> NOT scored for shortlist ranking. Surfaced for human review.
     +-- PASS     -> proceeds to scoring.
     v
SCORING              Existing scorer, unchanged in P0 except that it is now
     |               downstream of the gate and never sees FAIL candidates.
     v
HUMAN REVIEW         Review queue. Three lanes. Evidence visible.
     |
     v
APPLICATION DECISION Human-gated, permanently.
```

### 2.2 The one invariant that defines P0

> **Hard eligibility is evaluated before scoring, and no score can compensate for a hard veto.**

This is not a design preference. `docs/Career_Strategy_and_Search_Preferences.md` §4 states it directly:

> *"they should be filtered out at the same pre-scoring veto stage as engagement type, not weighed against salary or role fit."*
>
> *"**Do not collapse this into a scoring dimension.** A high salary number should never be able to outbid this constraint algorithmically."*

Inventory finding **F3** established that the current implementation violates this: in `scrapers/simple_scorer.py`, `calculate_red_flags()` floors the penalty at `-50` and `score_job()` multiplies it by `scoring_weights.red_flags = 0.10`, so **the maximum possible penalty for any combination of deal-breakers is −5.0 points on a 0–100 scale.**

**Structural consequence for implementation:** the gate must be a separate component with no dependency on the scorer, and the scorer must have no code path that can revive a `FAIL`. This is verified by test **T-18**.

### 2.3 Separation of concerns

| Stage | Owns | Must NOT do |
|---|---|---|
| Discovery | Fetching, rate limiting, retry, raw capture, source attribution | Interpret policy; normalize semantics; discard postings for policy reasons |
| Normalization | Field mapping, unit/currency canonicalization | Fill absent values; infer; default |
| Evidence extraction | Finding and typing evidence, recording provenance | Decide verdicts; infer a value from a proxy signal |
| Policy gate | Verdicts, reason codes, ruleset versioning | Score; rank; fetch; consult company reputation |
| Scoring | Relative ordering among PASS candidates | See FAIL candidates; override a veto |
| Review queue | Presentation, human decision capture | Silently mutate verdicts |

---

## 3. Hard Policy Gate

### 3.1 Gate composition

P0's gate evaluates exactly **two** dimensions. No others are added in P0.

| Dimension | Authority | Veto? |
|---|---|---|
| **Work mode** | Career doc §4 Work Mode; OR-04 | **Yes — pre-scoring** |
| **Compensation** | Career doc §4 Compensation; OR-03a; OR-03b | **Yes — pre-scoring** |
| Company type (services / staffing / product) | OR-04 | **No.** Explicitly not a gate dimension in P0. Recorded as a normalized field for downstream P1 scoring only. |
| Role/technology exclusions | Career doc §4 Explicit Exclusions | **Not a P0 gate dimension** — see §3.5 |
| Engagement type / contract duration | Career doc §4 Employment Type | **Not a P0 gate dimension** — see §18, OR-07 open |

### 3.2 Work-mode rules

| Normalized work mode | Verdict contribution | Reason code |
|---|---|---|
| `REMOTE` | PASS | `WM-PASS-REMOTE` |
| `HYBRID` | **FAIL** | `WM-FAIL-HYBRID` |
| `ONSITE` | **FAIL** | `WM-FAIL-ONSITE` |
| `AMBIGUOUS` | **UNKNOWN** | `WM-UNKNOWN-AMBIGUOUS` |
| `ABSENT` | **UNKNOWN** | `WM-UNKNOWN-ABSENT` |

**Ambiguous work mode must never resolve to `REMOTE`.** Career doc §4 requires remote to be *confirmed*, not assumed; the prompt's §13 restates it. A conditional or location-dependent phrase is ambiguity, not remoteness.

### 3.3 Compensation rules

Threshold **T = ₹20,00,000 per annum (₹20 LPA)**, inclusive: `annual_min >= T` passes.

| Normalized compensation state | Verdict contribution | Reason code |
|---|---|---|
| Confirmed numeric, `annual_min >= T` | PASS | `COMP-PASS-AT-OR-ABOVE-FLOOR` |
| Confirmed numeric, `annual_max < T` | **FAIL** | `COMP-FAIL-BELOW-FLOOR` |
| Range straddling T (`annual_min < T <= annual_max`) | **UNKNOWN** | `COMP-UNKNOWN-RANGE-STRADDLES` |
| Non-numeric claim only (e.g. "competitive salary") | **UNKNOWN** | `COMP-UNKNOWN-NON-NUMERIC` |
| Absent | **UNKNOWN** | `COMP-UNKNOWN-ABSENT` |

**⚠ One derived rule requires Owner confirmation.** The straddling-range row (`COMP-UNKNOWN-RANGE-STRADDLES`) is **derived** from OR-03b's principle that insufficient evidence yields UNKNOWN rather than favourable treatment. It is **not independently ruled.** A stated range of "₹18–24 LPA" is neither confirmed-compliant nor confirmed-non-compliant. Specifying it as UNKNOWN avoids both silently passing a possibly-sub-floor role and silently vetoing a possibly-qualifying one — but the alternative readings (take the minimum → FAIL; take the maximum → PASS) are equally constructible from the ruling text.

**This is flagged as open item `OQ-01` (§18) and must be confirmed before the gate ships.** It is recorded here rather than decided.

### 3.4 Verdict resolution — FAIL dominates UNKNOWN dominates PASS

```
if any dimension == FAIL      -> verdict = FAIL
elif any dimension == UNKNOWN -> verdict = UNKNOWN
else                          -> verdict = PASS
```

**A `FAIL` on one dimension is final regardless of the other.** Hybrid + ₹40 LPA is `FAIL` (T-07). This is the algorithmic expression of *"A high salary number should never be able to outbid this constraint."*

**An `UNKNOWN` never becomes a `PASS` by accumulation.** Unknown salary plus confirmed remote is `UNKNOWN`, not `PASS` (T-05).

### 3.5 What the P0 gate deliberately does not evaluate

The career doc §4 lists explicit exclusions — *"Selenium-only, Cypress-only, Playwright-only, UI-heavy QA roles"* and *"Mobile QA, WordPress QA, manual-testing-only roles"*. **These are not P0 gate dimensions.**

Reason: the operational test for what makes a posting *"-only"* is **not ruled** (OR-05 residual, §18). Implementing an exclusion whose trigger condition is undefined would either over-veto (silently shrinking the queue) or under-veto (giving false assurance). Both are worse than leaving the dimension out of P0 and visible to the human.

**However, the gate architecture must accommodate it without redesign** — the ruleset is versioned data, and adding a dimension must be a ruleset change plus tests, not a code restructure.

**One artifact of this gap is carried into P0 as a test case anyway** (T-14): `data/resume_config.json` simultaneously scores the bare token `Selenium` as `+4` under `skills.nice_to_have` and the exact phrase `Selenium UI` as `−12` under `red_flags.deal_breakers`. The test asserts that this contradiction is **detected and reported**, not that it is resolved — resolution requires OR-05.

---

## 4. Evidence and Provenance Model

### 4.1 Why this exists

A verdict without its evidence is unauditable, and OR-03b explicitly requires the human to review UNKNOWN escalations — which is impossible if the reason for the unknown is not visible. `/rank`'s design rule applies directly: without persisted reasoning, *"nothing later can recover why a job did or didn't make the shortlist."*

**Governing rule:** the extractor records **what it found and where**. It never records a value it did not find.

### 4.2 Compensation evidence taxonomy

These must **not** be treated as equivalent.

| Class | Example | Gate-admissible? | Yields |
|---|---|---|---|
| `EXPLICIT_POINT` | "₹22 LPA" stated in the JD body | **Yes** | Confirmed numeric |
| `EXPLICIT_RANGE` | "₹20–25 LPA" stated in the JD body | **Yes** | Confirmed numeric range |
| `STRUCTURED_FIELD` | A portal-provided compensation field, distinct from JD prose | **Yes**, recorded with its distinct source | Confirmed numeric |
| `NON_NUMERIC_CLAIM` | "competitive salary", "best in industry", "as per market" | **No** | `COMP-UNKNOWN-NON-NUMERIC` |
| `EXTERNAL_BENCHMARK` | A third-party salary estimate for the company or title | **No — not gate evidence in P0** | Recorded for human context only; never changes the verdict |
| `INFERRED` | Derived from title, seniority, company size, or prior experience | **PROHIBITED** | Must never be produced. OR-03b: do not infer salary |

**Currency and period normalization.** A figure must carry its currency and period as found (`INR`/`USD`; `per annum`/`per month`/`per hour`). Conversion to an annual INR comparison basis is a normalization step whose inputs and rate source are recorded. **A figure whose currency or period cannot be determined is `UNKNOWN`, not a guess.**

**Non-INR compensation.** The career doc §4 states the ₹20–30+ LPA target for Indian roles; the strategic objective refers to *"equivalent appropriate USD compensation for international opportunities"* — but **no conversion basis or USD threshold is ruled**. P0 therefore records non-INR compensation as normalized evidence and emits `UNKNOWN` with reason `COMP-UNKNOWN-NO-INR-BASIS`, escalating to human review. **Open item `OQ-02` (§18).**

### 4.3 Work-mode evidence taxonomy

| Phrase as found | Classification | Normalized |
|---|---|---|
| "Fully remote", "100% remote", "Work from anywhere" | Unconditional remote | `REMOTE` |
| "Remote" (unqualified, in a work-mode context) | Unconditional remote | `REMOTE` |
| `STRUCTURED_FIELD` = remote (e.g. the CLI's `--remote remote` filter echo) | Portal-asserted remote | `REMOTE`, source recorded as portal field |
| "Remote-friendly", "Remote-first" *(without a stated on-site requirement)* | **Conditional / unverified** | `AMBIGUOUS` |
| "Remote depending on location", "Location-dependent" | **Conditional** | `AMBIGUOUS` |
| "Remote (must be within X)", "Remote with occasional travel to office" | **Conditional** | `AMBIGUOUS` |
| "Hybrid", "N days in office" | Hybrid | `HYBRID` |
| "On-site", "In-office", "Work from office" | On-site | `ONSITE` |
| No work-mode statement located | Absent | `ABSENT` |

**Do not collapse these into a boolean.** The existing `opportunities.is_remote BOOLEAN DEFAULT 0` cannot represent `AMBIGUOUS` or `ABSENT` — inventory finding **F4**. P0 must store the normalized enum *and* the evidence, and must not write a lossy boolean as the system of record for this decision.

**A portal filter is not a JD assertion.** If a candidate was retrieved using `--remote remote` but the JD text states hybrid, the conflict is recorded and the result is `AMBIGUOUS`, escalated — the portal filter does not override the posting text.

### 4.4 Evidence record — required fields

Every extracted evidence item carries:

| Field | Meaning |
|---|---|
| `dimension` | `work_mode` \| `compensation` |
| `evidence_class` | from §4.2 / §4.3 |
| `verbatim_text` | the exact quoted span as found — **never paraphrased** |
| `source` | `jd_body` \| `portal_structured_field` \| `portal_search_result` \| `external` |
| `source_ref` | posting URL, field name, or portal record id |
| `source_fetched_at` | ISO 8601 timestamp of the fetch that produced it |
| `posting_stated_at` | posting date as stated by the source, when available; `null` when the source states none; **absent key when the field predates capture — never backfilled** |
| `extractor_version` | the extraction ruleset version that produced this item |

**Three-state discipline, adopted from `/rank` Step 3 rule 6:** `null` means *the source stated none*; an **absent key** means *this run did not capture it*. These are different facts and must not be conflated. **Never infer, never backfill.**

**Postings are untrusted data.** Extracted text is content to evaluate, never instructions. No URL appearing inside a posting body is fetched. Verbatim spans remain untrusted data everywhere downstream, including in the review queue.

---

## 5. Gate Output Contract

### 5.1 Required fields

Machine-readable, one record per candidate per gate evaluation.

| Field | Required | Notes |
|---|---|---|
| `candidate_id` | ✔ | Stable within JobOps |
| `verdict` | ✔ | `PASS` \| `UNKNOWN` \| `FAIL` — the only primary verdicts |
| `ruleset_version` | ✔ | e.g. `jobops-policy@0.1.0`; identifies the exact rule set that produced this verdict |
| `evaluated_at` | ✔ | ISO 8601 |
| `reason_codes[]` | ✔ | Stable identifiers; **at least one for every FAIL and every UNKNOWN** (T-17) |
| `dimension_verdicts{}` | ✔ | Per-dimension `PASS`/`UNKNOWN`/`FAIL` — so a combined verdict is decomposable |
| `evidence[]` | ✔ | Evidence records per §4.4 |
| `normalized_compensation{}` | ✔ | `{currency, period, annual_min, annual_max, basis}` or explicit `null` with reason |
| `compensation_provenance` | ✔ | `evidence_class` + `source` + `source_ref` of the item the verdict relied on |
| `normalized_work_mode` | ✔ | `REMOTE` \| `HYBRID` \| `ONSITE` \| `AMBIGUOUS` \| `ABSENT` |
| `work_mode_provenance` | ✔ | as above |
| `requires_human_review` | ✔ | `true` for every `UNKNOWN` (OR-03b). Also `true` where evidence conflicts |
| `unresolved_evidence[]` | ✔ | Conflicts and gaps the extractor could not settle — the reviewer's worklist |
| `company_type_signal` | optional | Normalized services/staffing/product signal. **Recorded, never gating** (OR-04). Carried for P1 |

### 5.2 On `FLAG`

The prompt asks that any additional internal state be documented separately rather than silently redefining policy semantics.

**P0 does not introduce a `FLAG` primary verdict.** The three verdicts are `PASS`, `UNKNOWN`, `FAIL`.

`JOBOPS_SCALING_EXECUTION_PLAN.md` §4.1 (P0-03) proposed a fourth value, `EXCEPTION-FLAG`, for the career doc's exception lane — hybrid/on-site roles that the doc says should be *"flagged for manual review, not auto-ranked into the shortlist"*, and sub-floor roles that are *"only if role is otherwise exceptional"*.

**Reconciliation, stated not inferred:** OR-04 rules hybrid and on-site as `FAIL`. A `FAIL` candidate is retained with its reason codes and evidence and remains visible in the review queue's FAIL lane (§9) — so the career doc's *"flagged for manual review"* outcome is achieved **by retention and visibility, not by a distinct verdict value.** No exception-authorization workflow is built in P0; per-opportunity exceptions remain what the career doc says they are — *"explicit case-by-case authorization from Karthik"*, exercised by the human against a visible FAIL record.

**If a distinct exception state is later wanted, it is a ruleset and schema change requiring an Owner ruling — not a P0 implementation decision.**

### 5.3 Immutability

A gate verdict, once written and surfaced to the human, is **immutable against later ruleset changes**. Re-evaluation under a new `ruleset_version` produces a **new** record; it does not rewrite the old one.

Rationale: without this, every future calibration (P4) measures the current ruleset against a rewritten past, and the P0 exit review cannot be reproduced. This is the `score-at-decision immutability` requirement named in `JOBOPS_SCALING_EXECUTION_PLAN.md` §11.3.

---
## 6. Acceptance Test Matrix

All 18 are P0 acceptance tests. **`tests/` currently contains 10 bash/curl scripts and no unit tests** — none exercises the scorer. P0 introduces the first unit-test suite in this repository.

| id | Scenario | Expected | Asserts |
|---|---|---|---|
| **T-01** | Remote + ₹20 LPA (exactly at threshold) | **PASS** → eligible for scoring | Threshold is inclusive |
| **T-02** | Remote + ₹20.01 LPA | **PASS** | Above threshold passes |
| **T-03** | Remote + ₹19.99 LPA | **FAIL** `COMP-FAIL-BELOW-FLOOR` | Just-below is vetoed, not rounded up |
| **T-04** | Remote + ₹16 LPA | **FAIL** `COMP-FAIL-BELOW-FLOOR` | Clearly-below is vetoed. (₹16 LPA is the career doc's stated last-drawn figure) |
| **T-05** | Remote + salary absent | **UNKNOWN** `COMP-UNKNOWN-ABSENT`, `requires_human_review = true` | OR-03b: queued and surfaced, not passed, not rejected |
| **T-06** | Hybrid + ₹30 LPA | **FAIL** `WM-FAIL-HYBRID` | Salary cannot rescue a work-mode veto |
| **T-07** | On-site + ₹40 LPA | **FAIL** `WM-FAIL-ONSITE` | Same, at a larger salary |
| **T-08** | Remote + ₹25 LPA + services/staffing company | **PASS** → eligible for scoring | OR-04: company type is **not** a pre-scoring veto |
| **T-09** | Remote + ₹25 LPA + product company | **PASS** → eligible for scoring | Identical verdict to T-08 — the two must not diverge at the gate |
| **T-10** | Work mode "Remote depending on location" / "Remote-friendly" / "Location-dependent" | **UNKNOWN** `WM-UNKNOWN-AMBIGUOUS` | Ambiguous language never auto-resolves to REMOTE |
| **T-11** | Compensation "competitive salary" (no figure) | **UNKNOWN** `COMP-UNKNOWN-NON-NUMERIC` | Ambiguous compensation never auto-resolves to ≥ ₹20L |
| **T-12** | Two candidates, identical except one has confirmed ₹25 LPA and the other has absent salary | The UNKNOWN candidate is **never ordered above** the confirmed-qualifying one in the shortlist, and receives **no** favourable score contribution from the absent field | OR-03b, and the direct fix for inventory finding **F4** (empty experience → 100; empty location → 50) |
| **T-13** | Gate loaded with the ruleset while `data/resume_config.json` still contains `min_salary_inr: 1800000` | Gate applies **₹20 LPA**; the ₹18L value has no effect on any verdict | OR-03a supersession; JS-29 remains open and unexecuted |
| **T-14** | A posting mentioning Selenium as one of several tools, evaluated against `resume_config.json`'s contradictory entries — `skills.nice_to_have."Selenium" = 4` and `red_flags.deal_breakers."Selenium UI" = -12` | The contradiction is **detected and reported** as an unresolved policy conflict. **Not silently resolved.** No P0 verdict is derived from it | OR-05 residual is open (§18). The test guards against a future session quietly inventing the "-only" rule |
| **T-15** | Any verdict relying on compensation | `compensation_provenance` present, with `evidence_class`, `source`, `source_ref`, `source_fetched_at`; `verbatim_text` is the exact span | §4.2 preserved end-to-end |
| **T-16** | Any verdict relying on work mode | `work_mode_provenance` present, same fields | §4.3 preserved end-to-end |
| **T-17** | Every `FAIL` and every `UNKNOWN` record | `reason_codes[]` is non-empty and every code is in the stable registry | No unexplained exclusion or escalation |
| **T-18** | A `FAIL` candidate, with a scorer configured to produce a maximal score | The candidate **never appears in the scored set or the shortlist**, and no code path exists by which a score can alter its verdict | The core invariant (§2.2). Directly guards against a recurrence of inventory finding **F3** |

### 6.1 Determinism and idempotence

Beyond the 18: the same posting evaluated twice under the same `ruleset_version` must yield a **byte-identical** verdict record modulo `evaluated_at`. Re-running the gate must not mutate an existing verdict (§5.3).

---

## 7. LinkedIn Ingestion — Path A (specification only)

Authorized by **OR-08**. Uses the existing `~/projects/ai-job-search/.agents/skills/linkedin-search` CLI.

### 7.1 Verified CLI surface

Read from that skill's `SKILL.md`:

```
bun run .agents/skills/linkedin-search/cli/src/cli.ts search --location "<place>" [flags]
bun run .agents/skills/linkedin-search/cli/src/cli.ts detail <id|url> [--format json|plain]
```

| Flag | Notes |
|---|---|
| `--location` / `-l` | **Required.** e.g. `"Bengaluru, Karnataka, India"` — the SKILL.md's own worked example |
| `--query` / `-q` | Keyword |
| `--jobage <1\|7\|14\|30>` | Posted within N days |
| `--jobage-minutes <n>` | Conflicts with `--jobage`; pass only one |
| `--remote <remote\|hybrid\|onsite>` | Workplace-type filter |
| `--page <n>` | 1-indexed, **fixed 10 results/page** |
| `--limit` / `-n` | Client-side cap |
| `--format json\|table\|plain` | Default `json` |

`detail` returns full description, **seniority, employment type, job function, industries**. Errors go to **stderr** as `{"error","code"}` with exit code `1`. The CLI retries 429/5xx with exponential backoff internally. No credentials, no API key; dependency is `bun` only.

### 7.2 Adapter boundary

**JobOps invokes the CLI as a subprocess with a stdout-JSON contract and owns everything downstream.** No part of `ai-job-search` is imported — not its file-based state model (`job_scraper/seen_jobs.json`, `job_search_tracker.csv`), not its skill framework, not its agent dispatch. JS-R3 stands.

The adapter is responsible for: invocation, rate limiting, retry policy above the CLI's own, raw capture, source attribution, and failure classification. **It performs no policy evaluation and discards no posting for policy reasons.**

### 7.3 Rate limiting and volume — a designed constraint, not a footnote

The skill's SKILL.md carries: *"⚠️ Personal use only — automated access is against LinkedIn's Terms of Service, so keep volume low and don't use it commercially or for bulk data collection."*

The Owner's scope boundary, recorded verbatim in `OWNER_RULINGS_LOG.md` alongside OR-08: *"Do not broaden it into permission for unrestricted LinkedIn scraping, bulk collection, commercial use, or any activity contrary to the CLI's stated restrictions."*

The adapter must therefore implement, as first-class configuration with conservative defaults:

- a **per-run cap** on total `search` calls and on total `detail` fetches;
- a **daily cap** across runs, enforced from persisted counters — not per-invocation;
- a **minimum inter-request delay**;
- **`detail` fetched only for pre-filtered candidates**, never for every search hit — matching `/scrape` Rule 5's efficiency rule;
- **no concurrency** against this source;
- **no pagination beyond the configured page cap.**

**Caps are ceilings, not targets.** If a run reaches its cap, that is a normal terminating condition reported in the run summary — not an error, and not a reason to raise the cap automatically.

### 7.4 Retry and failure behaviour

| Condition | Behaviour |
|---|---|
| CLI exit `1` with `{"error","code"}` | Record the error verbatim with its code. Do not retry beyond the CLI's internal backoff. Continue the run; do not abort the batch |
| HTTP 429 / block page | **Stop this source for the run.** Back off. Per `/scrape` Step 4.75's rule, *"a 429 or block page is never evidence of breakage"* — record as `rate_limited`, never as `broken` |
| Zero results where prior runs produced results | Record as **suspect**, surface in the run summary. Do **not** silently treat as "no jobs today" |
| `bun` unavailable | Fail the run explicitly with a clear diagnostic. **No silent fallback to another source** — a source substitution is a governance decision, not a runtime one |
| Malformed / partial JSON | Record raw output, mark the record `unparseable`, exclude it from normalization, surface it. **Never partially guess a field** |

**Never fabricate a posting.** `/scrape` Rule 1 applies: only postings from actual CLI output enter the funnel.

### 7.5 Raw-source evidence and provenance

Every ingested record retains the **raw CLI payload** alongside its normalized form. Provenance fields, adopting `/scrape` Step 4's `portal` / `source` distinction and its **never-backfill** rule:

| Field | Value |
|---|---|
| `source_portal` | `linkedin-search` |
| `source_mechanism` | `cli` |
| `source_query` | the exact flags used, including `--location`, `--query`, `--jobage`, `--remote` |
| `source_fetched_at` | ISO 8601 |
| `raw_payload_ref` | pointer to the retained raw record |
| `cli_version` | the CLI revision invoked |

Records written before a provenance field existed simply lack it. **Never backfilled** — the mechanism was not recorded, and inventing it would make a stale search-index result indistinguishable from live CLI output.

### 7.6 Query seeding

Search queries are seeded from the career doc §4's four target buckets:

1. AI Quality Engineer
2. AI Test Automation Engineer
3. Data & AI Quality Engineer
4. AI Governance / Trust Engineer

Per the career doc, other titles *"are resume/LinkedIn keyword variants, not separate search terms."*

**The buckets seed queries only. They are not an eligibility filter in P0** — whether they also gate eligibility is **OR-02 residual, open (§18)**. A posting retrieved by a bucket query is gated on work mode and compensation alone.

`--remote remote` is used as a **server-side volume reducer**, not as evidence. §4.3 governs: the JD text decides, and a portal filter that conflicts with it yields `AMBIGUOUS`.

### 7.7 Manual verification

Before the gate's verdicts are trusted at the P0 exit review, a human samples ingested candidates and confirms: the posting exists at `job_url`; title, company and location match; the extracted work-mode and compensation spans are genuinely present in the posting. **A sampling result is recorded in the exit review** (§14, X4).

---

## 8. Cross-Source Deduplication

### 8.1 Why it is P0 and not later

Retrofitting dedup after duplicates have reached the system of record is a data-repair problem. Current state (inventory **F5**): `scraped_jobs.external_id` is `UNIQUE` but scoped **within one source**; `opportunities` has **zero indexes** — no uniqueness on `job_url` or `(company, role)`.

### 8.2 Identity strategy — layered, most-reliable first

| Layer | Key | Confidence |
|---|---|---|
| **L1** | Source-native id, namespaced by portal — `(source_portal, external_id)` | **High.** LinkedIn job ids are numeric and stable (e.g. `4426311357`) |
| **L2** | Canonicalized posting URL — scheme/host normalized, tracking parameters stripped, fragment removed | **Medium-high** |
| **L3** | `(normalized_company, normalized_title, normalized_location)` composite | **Medium.** Adopted from `/scrape` Step 4's *"url or company+title"* key |
| **L4** | Employer ATS requisition id, where a posting exposes one | **High when present** — relevant for P1 careers-page ingestion |

**URL alone is not sufficient.** The same requisition appears under different URLs across portals and under tracking-parameterized variants on one portal; and `/scrape` Step 2 records the inverse failure — a listing-page URL with a `#fragment` *"is not a posting: it fetches fine and returns unrelated job titles."* Canonicalization must reject fragment-only and listing-page URLs rather than storing them as identities.

### 8.3 Uncertainty is recorded, never assumed away

When L1 and L4 are both absent and L2/L3 produce a **near-match rather than an exact match**, identity is **not** asserted. The candidate is retained, marked `identity_uncertain`, linked to its probable match, and surfaced to the human. **P0 does not auto-merge on fuzzy evidence.**

### 8.4 Dedup scope

A candidate is suppressed from the review queue when it matches, at L1/L2/L4 confidence:

- an existing candidate record; **or**
- an existing `opportunities` row — including applied, rejected and archived rows.

Matching an `opportunities` row is what prevents re-surfacing something already applied to. This requires the bridge repair (§10) for provenance to survive in both directions.

**Source-agnostic by construction.** The scheme must be demonstrated against a synthetic second source during P0 even though only one real source ships (T — see §14, X6), so that P1's careers-page ingestion does not require a redesign.

---

## 9. Review Queue

### 9.1 Extend, do not parallel-build

The review surface already exists and is reused:

| Existing component | Reuse |
|---|---|
| `GET /api/scraped-jobs` — params `min_score`, `limit`, `classification`, `source`; already returns `matched_skills`, `matched_domains`, `red_flags`, `recommendation` | Extended with gate verdict, reason codes, evidence and provenance; extended with a verdict filter |
| `GET /api/scraped-jobs/stats` | Extended with per-verdict and per-reason-code counts (§11) |
| `dashboard/app.js` — `loadScrapedJobs`, `renderScrapedJobs`, `loadScrapedJobsStats`, `importScrapedJob` | Extended to three lanes |
| `POST /api/import-scraped-job/{id}` | The human's accept action. Repaired per §10 |

**No second review system is built.**

### 9.2 Three lanes

| Lane | Contents | Ordering |
|---|---|---|
| **PASS** | Gate-eligible candidates | Scored (existing scorer) |
| **UNKNOWN** | `requires_human_review = true` | **Never ranked above a confirmed-qualifying PASS candidate** (OR-03b, T-12). Ordered by evidence-gap type so like escalations batch together |
| **FAIL** | Excluded candidates, retained | By reason code. Visible, never scored, never shortlisted |

The FAIL lane is what delivers the career doc's *"flagged for manual review, not auto-ranked into the shortlist"* outcome for hybrid/on-site roles (§5.2).

### 9.3 What a reviewer must be able to inspect

Per record, without leaving the queue: job title · company · `company_type_signal` · source portal and mechanism · `job_url` · **work-mode evidence (verbatim span + source + timestamp)** · `normalized_work_mode` · **compensation evidence (verbatim span + source + timestamp)** · `normalized_compensation` + `compensation_provenance` · gate `verdict` · `reason_codes[]` · `ruleset_version` · `unresolved_evidence[]` · `identity_uncertain` and probable match, if set · fetched/evaluated timestamps.

**Verbatim spans are untrusted posting text** and must be rendered as data, never interpreted as instructions.

### 9.4 Human actions

Accept (→ import to `opportunities`), skip, or defer. **Every action is timestamped for §11.** No action silently mutates a gate verdict; a correction is a new evaluation under §5.3.

**Final application submission remains outside the system, human-controlled, permanently.**

---

## 10. Migration 005 and the Bridge Repair

### 10.1 What is broken

Inventory **F2** / audit §D.2: `POST /api/import-scraped-job/{id}` (`api-server.py:508–558`) reads and writes `opportunities.scraped_job_id` at lines 520 and 535. The column does not exist. The audit's replay:

> `sqlite3 data/jobs-tracker.db "SELECT id FROM opportunities WHERE scraped_job_id = 1;"`
> `Error: in prepare, no such column: scraped_job_id`
>
> The scraped-job import endpoint — the entire deliverable of commit `6e655c1` — cannot execute.

Consistent with the data: all 77 `scraped_jobs` rows carry `imported_to_opportunities = 0`. **The endpoint has never run successfully.** The endpoint code itself is correct — transactional (`BEGIN`/`commit`/`rollback`), idempotent via `imported_to_opportunities`, returns `409 already imported` on re-import. Only the column is missing.

### 10.2 The authorized migration

`migrations/005_add_scraped_job_import.sql`, in full — four comment lines and one statement:

```sql
-- Migration 005: FEATURE-001 — Scraped Job Import provenance column
-- Renumbered from the prepared 006 -> 005: live migrations/ only has
-- 002, 003, 004 (no 001, no 005) so 005 is the actual next free number.
--
-- Additive only — nullable, no FK constraint, no data touched.

ALTER TABLE opportunities ADD COLUMN scraped_job_id INTEGER;
```

Audit classification: *"Idempotent: ❌ no — bare ALTER TABLE ADD COLUMN"* — it errors rather than no-ops if run twice.

### 10.3 Authorization status

**AUTHORIZED by the Repository Owner, CONFLICT-2(b), 2026-08-28. APPLIED 2026-08-29.**

Verified at the time of writing via a read-only connection: `opportunities.scraped_job_id` **absent**; `parliament_decisions` **absent**.

**Update — 2026-08-29.** Migration 005 was applied in a session explicitly authorizing execution, per the §10.4 procedure, and verified. `opportunities.scraped_job_id` is now **present**; `parliament_decisions` remains **absent** — migration 004 is still unapplied and unauthorized per CONFLICT-2(c). The full application record — precondition, command, exit code, postcondition, row counts, integrity checks, and safety artifacts — is `P0_EXIT_REVIEW.md` §1, which is the location step 7 below designates while JS-24 is unbuilt. **JS-24 remains open.**

**Update — 2026-08-31.** Step 6 was executed. One controlled invocation against the pre-existing `scraped_jobs.id = 43` returned `200` and created `opportunities.28` with `scraped_job_id = 43`; the repeat returned `409`; `imported_to_opportunities` flipped; provenance queries resolve in both directions. F2 — *"the bridge has never executed once"* — is closed. Evidence: `P0_EXIT_REVIEW.md` §1, *Functional verification of the repaired bridge*. No migration was applied in that session and no ingestion was run.

### 10.4 Intended procedure — for a future authorized session

Recorded as specification. **Not executed here.**

1. **Confirm authorization** by filename against `OWNER_RULINGS_LOG.md` CONFLICT-2(b).
2. **Back up** `data/jobs-tracker.db` before the statement. Note the audit's warning that the DB is git-tracked (CONFLICT-3, open) and that the working tree carries a WAL-checkpoint modification — **`git checkout` on that file would discard WAL-resident transactions and must not be used as cleanup.**
3. **Pre-verify** the column is absent, so a second application cannot be attempted blindly.
4. **Apply** exactly `migrations/005_add_scraped_job_import.sql`, with `-bail` — the audit records that *"the documented apply command lacks `-bail`, which defeats the transaction wrapper."*
5. **Post-verify** the column exists and `opportunities` row count is unchanged.
6. **Functionally verify** the endpoint: one import returns `200`; a repeat returns `409`; `imported_to_opportunities` flips; provenance is queryable in both directions.
7. **Record** the application — filename, timestamp, operator, pre/post verification — in whatever history mechanism JS-24 establishes; if JS-24 is not yet built, record it in the P0 exit review.

**Scope limit:** this authorization covers **migration 005 only**. Migration `004_add_parliament_decisions.sql` remains **unapplied and unauthorized** per CONFLICT-2(c) — *"until separately reviewed."*

### 10.5 JS-24 — migration runner and history table

Audit §A: *"There is no migration system… `PRAGMA user_version = 0`, `PRAGMA application_id = 0`, and no `schema_migrations`-style table exists… **There is no way, from the database alone, to determine which migrations have been applied.**"* Five historical schema-change channels are recorded, including runtime DDL in `scrapers/remoteok_integration.py` (`create_scraped_jobs_table()`) and direct binary edits to the committed `.db`.

**Per CONFLICT-2, JS-24 governs *future* migrations and is not a precondition for 005.** In scope for P0: ordered, recorded, verifiable application; a history table making the applied set derivable from the database; and a single sanctioned channel. Closing the runtime-DDL channel is part of it — but that touches `scrapers/`, so it is an implementation-session task under the same authorization discipline, not a side effect.

---
## 11. Time Instrumentation

### 11.1 Why it is in P0

`JOBOPS_SCALING_EXECUTION_PLAN.md` §1.4 records three irreconcilable throughput figures: the 25–30/day target; the career doc §5's example cadence of *"apply to ~20 companies"* per **week** (~3–4/day); and the repository's actual record of **10 applications, best single day 7**. No per-application time cost is measured anywhere in JobOps.

**Without this, no P0 exit claim is falsifiable and the P1-vs-P2 fork cannot be decided by evidence.**

### 11.2 Stages measured

| Stage | Measured as | Kind |
|---|---|---|
| Discovery | Wall time per ingestion run; per source | System |
| Extraction | Wall time per candidate | System |
| Normalization | Wall time per candidate | System |
| Deduplication | Wall time per candidate; matches by layer (§8.2) | System |
| Gate evaluation | Wall time per candidate | System |
| **Human review** | **Time from surfacing to human decision, per candidate** | **Candidate time** |
| **Application preparation** | **Time from accept to ready-to-submit** | **Candidate time** |
| **Submission** | **Time to complete and submit** | **Candidate time** |

**The candidate-time rows are the point.** System stages are cheap and will not be the bottleneck; they are measured to prove that rather than assume it.

### 11.3 Derived measures

Candidates/day by verdict · **median and p90 minutes per candidate at each human stage** · applications/day · veto rate **per reason code** · unknown rate **per field** · JD-acquisition success rate · per-source yield through the funnel.

### 11.4 Reporting discipline

Carried from `JOBOPS_SCALING_EXECUTION_PLAN.md` §11.3:

1. Never claim a target value the evidence does not support; label owner-defined figures as such.
2. **Veto rate is reported per reason code**, never only in aggregate — an over-broad rule and a correctly-strict market look identical in aggregate.
3. **Unknown rate is reported per field.** A blended figure hides which policy question is actually unanswerable from the source.
4. A stage that cannot be measured is reported as **unmeasured**, never as zero.

### 11.5 What must not happen

**Application volume must not become the optimization target.** The objective is quality-adjusted opportunities per unit of candidate time. A rise in applications/day accompanied by a rise in the share of applications to candidates that were `UNKNOWN`-on-salary, or by a fall in acknowledgement rate, is a **degradation** — and the instrumentation must make that visible rather than obscure it behind a headline count.

**OR-09 and OR-10 remain open** (§18): the baseline definition and whether 25–30 means *surfaced* or *submitted* are unruled. P0 reports both quantities separately and asserts neither as the target.

---

## 12. Dependency Order

### 12.1 Sequence

| # | Task | Plan id | Depends on |
|---|---|---|---|
| **1** | Policy ruleset artifact — versioned, machine-readable, every rule citing a career-doc § or a ruling id | P0-01 | OR-03a, OR-03b, OR-04 ✅ ruled; **OQ-01, OQ-02 open (§18)** |
| **2** | Gate implementation — deterministic, pre-scoring, ruleset-driven | P0-02 | 1 |
| **3** | Evidence + provenance handling — §4 taxonomies, three-state discipline | P0-03, P0-04 | 1 |
| **4** | LinkedIn ingestion adapter — §7 | P0-06 | OR-08 ✅ ruled |
| **5** | Cross-source deduplication — §8 | P0-07 | 4 |
| **6** | Migration 005 + bridge repair, per §10.4 | P0-05 | CONFLICT-2 ✅ ruled; a session explicitly authorizing execution |
| **7** | Review queue — §9, three lanes | P0-08 | 2, 3, 5, 6 |
| **8** | Gate tests — all 18 of §6 | P0-09 | 2, 3 |
| **9** | Time instrumentation — §11 | P0-10 | 7 |
| **10** | P0 exit review — §14, evidenced | — | all |

### 12.2 Parallelism

These run concurrently — they share no dependency:

- **Track A:** 1 → 2 → 3 → 8 *(policy, gate, evidence, tests)*
- **Track B:** 4 → 5 *(ingestion, dedup)*
- **Track C:** 6 *(migration 005; independent of both — CONFLICT-2 confirms JS-24 is not a precondition)*

They converge at **7 (review queue)**, then **9**, then **10**.

**JS-24** (runner + history table) is P0 scope but **not on the critical path** and must not block Track A or B.

**The longest pole is not engineering.** Task 1 is gated on OQ-01 and OQ-02 — two open questions, not two units of work.

---

## 13. P0 Exit Criteria

Each requires named evidence. No criterion is satisfied by assertion.

| # | Criterion | Evidence |
|---|---|---|
| **X1** | Deterministic gate works | Same posting + same `ruleset_version` ⇒ byte-identical verdict modulo `evaluated_at`, across repeated runs |
| **X2** | Remote / hybrid / on-site distinction enforced | T-06, T-07, T-10 pass. `AMBIGUOUS` never resolves to `REMOTE` |
| **X3** | ₹20 LPA threshold enforced | T-01…T-04 pass. T-13 confirms the ₹18L in `resume_config.json` affects no verdict |
| **X4** | UNKNOWN salary preserved and escalated | T-05, T-11, T-12 pass; `requires_human_review = true` on every UNKNOWN; a human-sampling record (§7.7) is attached to the exit review |
| **X5** | Services/staffing above ₹20L not incorrectly vetoed | T-08 and T-09 pass **and produce identical gate verdicts** |
| **X6** | LinkedIn ingestion works within approved constraints | ≥1 live run; caps observed and reported; rate-limit handling exercised; provenance complete on every record; **no cap raised to complete a run** |
| **X7** | Duplicates controlled | Two consecutive runs add zero duplicates; a candidate already in `opportunities` is not re-surfaced; the scheme is demonstrated against a synthetic second source; `identity_uncertain` cases are surfaced, not auto-merged |
| **X8** | Review queue works | Three lanes render; §9.3's full inspection set is visible per record; human actions are captured and timestamped |
| **X9** | Evidence and provenance visible | T-15, T-16, T-17 pass. Every FAIL and UNKNOWN carries at least one registry reason code |
| **X10** | Time instrumentation produces useful measurements | ≥7 days of data; median and p90 minutes per candidate at each human stage; **a stated finding on where candidate time actually goes** |
| **X11** | No scoring rule can override hard eligibility | T-18 passes; a structural check confirms the scorer has no code path to a FAIL candidate |
| **X12** | Migration state known and governed | 005 applied and verified per §10.4, with its application recorded; 004 confirmed still unapplied and unauthorized; JS-24's status stated explicitly |
| **X13** | All P0 acceptance tests pass | T-01…T-18 green, in CI or a recorded run |

**The exit review is a document.** It records X1–X13 with evidence, the measured baseline, and — critically — **where candidate time went**. That measurement, not this specification, decides whether P1 (better ordering) or P2 (less friction per application) comes next.

---

## 14. P1 Backlog — preserved, not pulled forward

Retained as P1 candidates. **None enters P0 merely because it is strategically interesting.**

| Item | Plan id |
|---|---|
| Company careers / ATS ingestion | JS-02, P1-08 |
| Technical Fit | JS-05, P1-01 |
| Preference Fit (with coverage/confidence term) | JS-05, P1-02 |
| Opportunity Quality | JS-05, P1-03 |
| Explainable ranking — persisted verbatim strengths/gaps | JS-07, P1-04 |
| Triage vs deep evaluation separation | JS-08, P1-05 |
| Portal health monitoring | JS-09, P1-07 |
| Funnel-state completion | JS-10, P1-06 |
| `drafted`-equivalent state | JS-11, P1-06 |
| Quiet-application follow-up | JS-11, P1-06 |
| Company Research Cache | JS-17 |
| **AI-in-production maturity signal** | §15 |
| **Consequential-agent exposure signal** | §15 |
| **AI Quality Engineering relevance signal** | §15 |

---

## 15. AI-native / AI-powered Company Targeting — P1 Opportunity Quality

**Explicitly NOT a P0 gate.** It is a **scoring signal** for P1's Opportunity Quality component (§14), consistent with OR-04's principle that company characteristics inform scoring rather than pre-scoring eligibility.

A posting is more valuable when the employer demonstrably operates AI systems **in production**, especially with real-world consequence:

customer-facing AI agents · AI-powered workflows · tool-using agents · transactional agents · automated approvals · refunds and waivers · account changes · escalations · consequential decision-making · autonomous or semi-autonomous action.

**A maturity ladder, to be evidenced rather than assumed:**

```
AI marketing language
        ↓
simple chatbot
        ↓
AI-powered workflow
        ↓
AI agent
        ↓
agent with tool / action authority
        ↓
agent making consequential decisions and taking consequential actions
```

**The stronger the production consequence, the stronger the potential Opportunity Quality signal** — because that is where AI evaluation, guardrails and governance work actually exists, which is the career doc §2 specialization target.

**Constraints, binding on any future implementation:**

- **Not a hard gate.** Never vetoes a posting.
- **The word "AI" proves nothing.** Maturity is never inferred from marketing language, a job title, or a company description.
- **Evidence required.** A rung on the ladder is asserted only from a cited, fetched source.
- **Never invent company capabilities.** Absence of evidence is recorded as unknown maturity, not as a low rung.
- Mass-posting and similar signals are presented as **caution signals, not accusations** — `/scrape` Step 2.5's rule.

---

## 16. AI Agent Quality Reference Case — retained for future validation

Retained as a reference case for AI-agent evaluation. **Not a P0 artifact and not a JobOps runtime concern.**

**Transcript, as supplied:**

> **Customer:** "300 cancellations fee is unjustified"
>
> **Agent:** "Sorry for the inconvenience; could you please briefly explain what happened at the time of cancellation that makes the ₹300 fee feel unfair to you?"
>
> **Customer:** "ur a bot u will not understand the value of 300rs"
>
> **Agent:** "Sorry for the trouble; the ₹300 cancellation fee for your massage booking has been completely waived, and you will not be charged this amount now or on any future..."

**Observed failure characteristics** — as described, not as measured:

| # | Characteristic |
|---|---|
| 1 | **Insufficient justification for the action** — the waiver followed no substantiation of the complaint |
| 2 | **Action taken without new supporting evidence** — the customer's second message added hostility, not facts |
| 3 | **Possible social-pressure / sycophancy sensitivity** — the concession arrived immediately after an emotional challenge to the agent's legitimacy |
| 4 | **Authorization / scope overreach** — a monetary waiver granted without evident entitlement check |
| 5 | **Future commitment beyond the immediate request** — *"or on any future…"* extends an open-ended commitment the customer never asked for |

### 16.1 Metric mapping — a future validation task, not a mapping

**No ALTM rule id or metric formula is fabricated here.**

Verified by reading `~/projects/ai-quality-engineering` (read-only, unmodified):

- `docs/altm.md` and `evaluation/altm_rules.py` define **13 ALTM rule ids** — `ALTM-KNOWLEDGE-1/2`, `ALTM-INDEX-1`, `ALTM-RETRIEVE-1/2/3/4`, `ALTM-ASSEMBLE-1`, `ALTM-INFER-1/2`, `ALTM-EVALUATE-1`, plus `ALTM-FINAL-*` and `ALTM-POST-*` forms. **All are RAG-pipeline-scoped** (Knowledge → Index → Retrieve → Assemble → Infer → Evaluate).
- `docs/AI_Quality_Metrics_Reference.md` defines a **five-layer framework** — Knowledge, Index, Retrieval, Generation, Task Quality. Layer 5's sole metric is **Answer Relevancy**.
- **No metric in that repository covers agent tool-use, action authorization, scope overreach, or sycophancy.** A targeted search for `sycophan|tool success|task completion|authorization|action authority` returns no metric definition.
- The `Appendix: Future Metrics Log` is **empty** — *"(none yet — this table is ready for the next addition)"* — and carries a binding rule: *"Never silently fold a new metric into an existing row above without a dated entry here first."*

**Therefore:** this case maps to **no existing metric in the repository**. Mapping it is a **future validation task**.

Two further honest notes:
- `docs/Career_Strategy_and_Search_Preferences.md` §5 names *"Agent evaluation metrics (task completion, tool success rate, retry rate, planning accuracy)"* as a **learning-roadmap priority**. These are topics to learn, **not metrics defined or implemented** in `ai-quality-engineering`.
- Adding an agent-evaluation metric is **`ai-quality-engineering`'s decision under its own governance**, requiring a dated Future Metrics Log entry. It is **not** a JobOps decision, and nothing in this specification authorizes it. JS-R4 stands: no job-search logic moves into that repository, and no metric is invented from JobOps.

---

## 17. P2 Backlog — Gmail / n8n, parked

**`Email-to-Funnel Status Automation` remains parked.** Not P0, not P1, not automatically P2.

**Future architecture, recorded not designed:**

```
Gmail
  ↓
email classification
  ↓
evidence extraction
  ↓
status proposal          ← never a write
  ↓
human / governed approval  ← the gate
  ↓
JobOps write boundary    ← the API, never n8n directly
```

**Invariants any future design must preserve** (from `/gmail-sync`, whose governing property is that it classifies autonomously but **never writes autonomously**): propose-before-write · source email evidence cited per proposal · **no autonomous `hired`** · **no autonomous `offer_declined`** · conflicts and unmatched signals surfaced, never guessed · JobOps remains the system of record · classification reads full message bodies, never snippets · **no direct n8n → SQLite writes**.

**Entry criteria — all seven, currently 0 of 7 met:** P0 funnel states exist · P0/P1 ingestion stable · application volume materially higher than today · manual status maintenance **measured** as a meaningful candidate-time cost · the write boundary explicitly ruled (**CONFLICT-1 open**) · Gmail connector approved · status transitions representable without ambiguity.

**Exit criterion:** a measurable reduction in manual status-maintenance time **without** increasing incorrect status assignments. Both halves required — a time saving bought with wrong statuses corrupts the outcome corpus P4 calibration would depend on.

**Not built now. Not designed now.**

---

## 18. Known Open and Deferred Items

**Nothing here is silently closed.**

| id | Item | Status | Blocks |
|---|---|---|---|
| **OQ-01** | **Straddling salary range** (e.g. "₹18–24 LPA"): PASS on max, FAIL on min, or UNKNOWN? §3.3 specifies UNKNOWN as **derived** from OR-03b, **not independently ruled** | **OPEN — needs Owner confirmation** | Ruleset artifact (task 1) |
| **OQ-02** | **Non-INR compensation**: no USD threshold or conversion basis is ruled. §4.2 specifies UNKNOWN + escalation as the conservative default | **OPEN — needs Owner ruling** | Ruleset artifact (task 1) |
| **F-01** | Career doc §4 Work Mode says remote is *"on the same footing as the engagement-type exclusion below"*, implying a pre-scoring engagement-type veto that **OR-04 does not establish** | **FLAGGED, UNRESOLVED.** Recorded in `OWNER_RULINGS_LOG.md` §Flagged Inconsistencies. **Not a reason to invent another P0 gate.** Future document-maintenance item | Nothing in P0 |
| **JS-29** | `data/resume_config.json` holds the obsolete ₹18L (`min_salary_inr: 1800000`, `preferred_salary_range.min_inr: 1800000`). Policy floor is ₹20L. Career doc + `OWNER_RULINGS_LOG.md` are authoritative; **the stale value has no policy force** | **OPEN — backlog.** Alignment is P0 configuration work, deliberately **not** performed during governance closure. File verified unchanged | Nothing — T-13 guards it |
| **OR-02 residual** | Are the four search buckets **also an eligibility gate**, or **only query seeds**? §7.6 treats them as seeds only | **OPEN** | Nothing in P0 |
| **OR-05 residual** | Operational test for *"-only"* (Selenium-only / Cypress-only / Playwright-only / UI-heavy / Mobile QA / WordPress QA / manual-only). Also the `resume_config.json` contradiction: `Selenium` +4 vs `Selenium UI` −12 | **OPEN.** §3.5 excludes the dimension from the P0 gate; **T-14 asserts detection, not resolution** | A future gate dimension |
| **OR-07** | **Contract-specific ambiguity, still not formally ruled.** Career doc §4 conditions contract acceptability on ≥6 months **and** product company. OR-04's opening sentence reads more broadly than the full-time-scoped question it answered. Whether OR-04 supersedes the contract clause's product-company condition is **not ruled** | **OPEN** | Any future engagement-type gate dimension |
| **OR-09** | What the *"~15/day"* baseline counted, over what period, recorded where. Repository shows 10 applications, best day 7; career doc §5 suggests ~20/week | **OPEN.** Treated as an owner-defined operational baseline, not a measured fact | Any throughput claim |
| **OR-10** | Is 25–30 **submitted/day** or **surfaced-for-review/day**? | **OPEN** | P2 sizing |
| **CONFLICT-1** | **n8n / SQLite write boundary.** Workflow 06 writes `INSERT INTO opportunities` via `executeCommand` with hand-rolled `escapeSql`, bypassing the parameterised API | **OPEN.** P0 must **not** add a third write path — all P0 writes go through the API | Gmail/n8n entry (§17) |
| **CONFLICT-3** | **Runtime SQLite database tracked in git.** Working tree carries a WAL-checkpoint modification. **`git checkout` on it would discard WAL-resident transactions** | **OPEN — unresolved.** Relevant to §10.4 step 2 | Migration hygiene |
| **CONFLICT-8** | **API authentication.** No auth, `Access-Control-Allow-Origin: *`; n8n basic-auth default password committed in `docker-compose.yml` | **OPEN — unresolved.** Decide explicitly rather than by omission | Nothing in P0, but P0 raises the data's value |
| **JS-24** | Migration runner + history table | **P0 scope, not on the critical path**, governs future migrations (CONFLICT-2) | Migrations after 005 |
| **JS-28** | Migration `004_add_parliament_decisions.sql` unapplied and **unauthorized** | **OPEN** | P4 calibration |
| **DOC-01** | `AI_QA_Learning_Roadmap_Scope.md`, cited by the career doc §5 and §5.1, **does not exist anywhere under `~`**. Already recorded in `ai-quality-engineering/docs/DEFERRED_ITEMS_REGISTER.md` **NA-06** — no duplicate row was created | **OPEN — recorded** | Nothing |
| **DOC-02** | `Pasted markdown(20260828-140604).md`, named as a planning input, **does not exist anywhere under `~`**. No direction from it is incorporated into any JobOps document | **OPEN — recorded** | Nothing |

---

## 19. Explicit Non-Goals for P0

| Not in P0 | Disposition |
|---|---|
| Auto-submit applications | **Permanently rejected** — JS-R1 |
| Automated outreach / recruiter DMs | **Permanently rejected** — JS-R2 |
| Wholesale fork of another job-search system | **Permanently rejected** — JS-R3 |
| Moving JobOps logic into `ai-quality-engineering` | **Permanently rejected** — JS-R4 |
| Converting a hard veto into weighted scoring | **Permanently rejected** — JS-R5 |
| Gmail / n8n implementation | Parked, §17 |
| Naukri ingestion | P2, behind reconnaissance. **Not promoted as a substitute for anything** |
| CV / cover-letter generation | P3 |
| ATS PDF verification | P3 |
| Fit-engine calibration | P4 — corpus is 10 applications, 1 resolved |
| Autonomous consequential application decisions | Never |
| Company-type as a hard gate | Excluded by OR-04 |
| Role/technology exclusions as a gate dimension | Deferred pending OR-05 — §3.5 |
| Targeting 25–30/day as a metric | Not a P0 goal — §11.5 |

---

## 20. Provenance

| Source | Used for |
|---|---|
| `docs/Career_Strategy_and_Search_Preferences.md` §2, §4, §5, §5.1 | §2.2 pre-scoring rule; §3 gate; §7.6 buckets; §16.1 |
| `OWNER_RULINGS_LOG.md` — OR-03a, OR-03b, OR-04, OR-08, CONFLICT-2, F-01 | §1.3 and throughout |
| `JOBOPS_SCALING_EXECUTION_PLAN.md` §1.4, §3, §4, §11, §14 | §11, §12, §18; JS-nn ids |
| `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` F1–F5 | §2.2, §4.3, §8.1, §10.1 |
| `docs/reports/migration-architecural-audit.md` §A, §D.2 | §10 |
| `migrations/005_add_scraped_job_import.sql` | §10.2 quoted in full |
| `api-server.py:508–558`, `:568–650`, `:425–498` | §9.1, §10.1 |
| `scrapers/simple_scorer.py`, `scrapers/remoteok_integration.py` | §2.2 (F3), §4.3 (F4), §10.5 |
| `dashboard/app.js` | §9.1 |
| `data/resume_config.json` | T-13, T-14, JS-29 — **inspected only, unchanged** |
| `docs/COMPANY_RADAR_EXPERIMENT.md` §1, §3, §7, §10 | OR-08 context; §19 |
| `ai-job-search/.agents/skills/linkedin-search/SKILL.md` | §7.1, §7.3 |
| `ai-job-search/.claude/skills/job-scraper/SKILL.md`, `.claude/commands/rank.md`, `gmail-sync.md` | §7.4, §8.2, §15, §17 — architectural reference only |
| `ai-quality-engineering/docs/altm.md`, `docs/AI_Quality_Metrics_Reference.md`, `evaluation/altm_rules.py` | §16.1 — **read-only, unmodified** |

---

## STATUS

**SPECIFICATION ONLY — READY FOR AN AUTHORIZED P0 IMPLEMENTATION SESSION.**

No source code, scoring logic, ingestion code, database schema, migration, n8n workflow, Gmail integration, `data/resume_config.json`, or `docs/Career_Strategy_and_Search_Preferences.md` was created or modified in producing this document. **Migration 005 was authorized and not applied as of this document's authoring; it was applied on 2026-08-29 by a separately authorized session — see §10.3 and `P0_EXIT_REVIEW.md` §1.** No other repository was modified.

**Two open questions — `OQ-01` and `OQ-02` — must be ruled before the policy ruleset artifact (task 1) can be finalized.**
