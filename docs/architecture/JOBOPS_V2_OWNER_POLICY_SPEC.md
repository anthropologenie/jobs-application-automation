# JobOps v2 — Owner Policy Specification (policy v0.2.0, DRAFT)

**Phase:** A — specification only. **Nothing in this document is active.**
**Date:** 2026-09-29
**Machine-readable draft:** `docs/architecture/drafts/jobops-policy-0.2.0.draft.json`. It sits outside `policy/` on purpose: `policy/ruleset.py:35-37` loads only `policy/jobops-policy-0.1.0.json` and pins `EXPECTED_RULESET_VERSION = "jobops-policy@0.1.0"`.
**Rulings:** `OWNER_RULINGS_LOG.md` OR-11 … OR-30 (appended 2026-09-29)
**Open items:** `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md`
**Golden cases:** `tests/fixtures/policy_v02_golden_cases.json` (112 synthetic cases)
**Baseline assessment:** `docs/reports/JOBOPS_ACTIVATION_AUDIT_2026-09-29.md`

---

## 1. Authority and precedence

1. **Owner rulings recorded in `OWNER_RULINGS_LOG.md`.** OR-11 … OR-25 come from the Phase A specification. OR-26 … OR-30 are recorded **unruled**.
2. **This document and the draft JSON.** They encode those rulings. Where the owner did not decide, the item is listed in `JOBOPS_V2_OPEN_ITEMS.md` and the rule carries `owner_confirmed: false`.
3. **Superseded artifacts are preserved, not edited.** `policy/jobops-policy-0.1.0.json`, OR-03a, OR-04, OQ-01, the career document, `resume_config.json`, the scorer, the prompts and the resumes all stay unchanged. §9 maps each superseded rule to its replacement.

**Activation boundary.** v0.1.0 stays the only live policy until a separately authorized session does all of the following:

- implements a data-driven dimension loop (audit finding D2);
- passes the golden cases, skipping any case marked `OPEN:`;
- copies the draft into `policy/` and bumps the pinned version.

---

## 2. Current candidate profile (OR-11)

| Attribute | Value |
|---|---|
| Relevant AI industry experience | **3 years** |
| Relevant employers | Bosch, Happiest Minds, Ascendion |
| Employment location | India |
| Compensation anchor | Floor ₹18L; preferred ₹24–28L; ask ₹26L. **No anchoring to earlier compensation** |

The earlier QA Lead / ETL / Data Warehouse profile is **historical**. It is not an input to role search, experience matching, relevance, title matching, salary reasoning or ordering. The draft JSON encodes only the current profile.

---

## 3. Pipeline and separation of concerns (OR-13, OR-22)

```
DISCOVERY → OBSERVATION → EVIDENCE → IDENTITY/DEDUP → ELIGIBILITY → RELEVANCE → PREFERENCE
          → NEWNESS → QUEUE → HUMAN REVIEW → APPLICATION PREPARATION → HUMAN-GATED SUBMISSION
```

The pipeline produces five separate outputs. None is folded into another, and **there is no composite score** (PREF-R03).

| Output | Question | Values |
|---|---|---|
| Eligibility | Can the candidate actually take the job? | Six dimensions, each PASS / FAIL / UNKNOWN; overall FAIL > UNKNOWN > PASS (ELIG-R01) |
| Relevance | Does the work match the AI career direction? | STRONG / MODERATE / WEAK (plus state NOT_ASSESSED, OI-015), with evidence spans |
| Preference | How attractive is it relative to preferred conditions? | `compensation_band`, `employer_preference` |
| Newness | Is it genuinely new or materially changed? | NEW / UPDATED / SEEN_BEFORE |
| Review | Is a human decision still necessary? | Lane: SHORTLIST / REVIEW / PARKED / EXCLUDED / SUPPRESSED_DUPLICATE |

Experience and seniority are **fit signals** (DIRECT / REASONABLE / STRETCH / UNKNOWN_FIT; NONE … ARCHITECT). They never produce FAIL, and they never park a role by themselves.

---

## 4. Eligibility rules

Every rule has a stable ID. "Evidence required" names what must be stored before the verdict can be issued. Absent evidence yields UNKNOWN, never a favourable reading.

**Legend for the Confirmed column:**
- **Y** = owner-confirmed in the specification.
- **N** = pending an open item.
- **Carried** = inherited from a prior owner ruling or the v0.1 artifact.

### 4.1 Geography and work arrangement (OR-14, OR-15)

**Scope:** remote from India, plus Bengaluru hybrid. Relocation abroad is out of scope. "Global" means global *discovery*, not willingness to relocate.

| Rule | Condition | Verdict | Flag | Evidence required | Confirmed |
|---|---|---|---|---|---|
| GEO-N01 | Normalize Bengaluru aliases (Bengaluru, Bangalore, Bangalore Urban, Bengaluru Urban, Greater Bengaluru Area, Bengaluru East/North/South, any Bengaluru locality) via the geo alias table | normalization | — | location span + alias entry | Y |
| GEO-R01 | Remote worldwide | PASS | — | span stating worldwide/anywhere | Y |
| GEO-R02 | Remote, India explicitly eligible ("Remote – India", "India / US / UK", "eligible countries including India") | PASS | — | span naming India | Y |
| GEO-R03 | Remote, region-locked excluding India (US / EU / EEA / UK only) | FAIL | — | restriction span + region table | Y (EMEA: OI-029) |
| GEO-R04 | Requires foreign work authorization and India employment is not possible | FAIL | — | authorization span | Y |
| GEO-R05 | Remote eligibility ambiguous ("Remote – APAC" with India not named) | UNKNOWN | GEO_REGION_AMBIGUOUS | span + reason | Y (OI-011, OI-012) |
| GEO-R06 | Bengaluru hybrid, 0–3 office days/week | PASS | — | span with day count ≤ 3 | Y |
| GEO-R07 | Bengaluru hybrid, 4–5 office days/week | FAIL | — | span with day count ≥ 4 | Y (OI-013) |
| GEO-R08 | Bengaluru hybrid, days unspecified | UNKNOWN | HYBRID_DAYS_UNSPECIFIED | hybrid span | Y |
| GEO-R09 | "Flexible hybrid" (Bengaluru) | UNKNOWN | HYBRID_FLEXIBLE | span | Y |
| GEO-R10 | Bengaluru onsite | UNKNOWN | BENGALURU_ONSITE | onsite span | Y (OI-013) |
| GEO-R11 | Hybrid outside Bengaluru | FAIL | — | span + non-Bengaluru city | Y |
| GEO-R12 | Onsite in India outside Bengaluru | FAIL | — | span | Y |
| GEO-R13 | Onsite abroad | FAIL | — | span | Y |
| GEO-R14 | Relocation abroad | FAIL | — | span | Y |
| GEO-R15 | Visa-supported relocation | FAIL | — | span | Y |
| GEO-R16 | No work-arrangement statement anywhere | UNKNOWN | WORK_ARRANGEMENT_ABSENT | sought-and-not-found record | Carried (v0.1 WM-R5, OR-03b principle) |
| GEO-P01 | Precedence: FAIL rules are checked before PASS rules; ambiguity yields UNKNOWN; a qualified phrase never resolves to PASS | — | — | — | Y |

Bengaluru is **one rule over normalized geography**. It is not scattered through gate code (§29 of the Phase A specification; see `JOBOPS_V2_DATA_MODEL.md` §6).

### 4.2 Time zone (OR-16)

| Rule | Condition | Verdict | Stored |
|---|---|---|---|
| TZ-R01 | Any overlap requirement (US, UK, European, APAC) | **FLAG ONLY — never FAIL** | `timezone_requirement`, `timezone_overlap_flag`, `detected_timezone`, evidence |

Whether these flags route an item to REVIEW is OI-014. The draft treats them as informational.

### 4.3 Language (OR-17)

| Rule | Condition | Verdict | Flag | Confirmed |
|---|---|---|---|---|
| LANG-R01 | English posting, nothing else required | PASS | — | Y |
| LANG-R02 | Non-English language explicitly required ("German required", "French mandatory") | FAIL | — | Y |
| LANG-R03 | Non-English language nice-to-have / preferred / bonus | FLAG ONLY | LANGUAGE_PREFERENCE | Y |
| LANG-R04 | Whole JD non-English, confident detection | FAIL | — | Y (threshold OI-023) |
| LANG-R05 | Detection uncertain | UNKNOWN | LANGUAGE_UNCERTAIN | Y (threshold OI-023) |

### 4.4 Compensation (OR-18; OR-27 pending)

**Parameters:**
- floor ₹18,00,000 annual base;
- preferred band ₹24–28L;
- expected ask ₹26L;
- **one floor across all currencies**, with no separate USD/EUR floors.

**Basis:**
- Compare annual gross **base** only.
- Equity, stock, bonus, commission and sign-on amounts are ignored. If they are the only information given, the result is UNKNOWN.

**Stored fields (COMP-N01):**
`original_currency`, `original_amount`, `original_period`, `compensation_type` (BASE / CTC / TOTAL / BONUS / EQUITY / UNSPECIFIED), `base_or_total`, `fx_rate`, `fx_source`, `fx_snapshot_date`, `normalized_inr_annual_base`.

| Rule | Condition | Eligibility | Preference / flag | Confirmed |
|---|---|---|---|---|
| COMP-R01 | Clearly below ₹18L | FAIL | — | Y |
| COMP-R03 | ₹18L ≤ base < ₹24L (point, or range wholly inside) | **PASS** | BELOW_TARGET_BAND → lane REVIEW | Y (straddling ₹24L: OI-008) |
| COMP-R02 | ≥ ₹24L | PASS | IN_TARGET_BAND (24–28L) / ABOVE_TARGET_BAND (> 28L, OI-022) | Y |
| COMP-R04 | Range overlapping ₹18L (₹15–20L, ₹18–25L) | UNKNOWN | COMP_RANGE_OVERLAPS_FLOOR | Y (₹18L minimum: OI-006) |
| COMP-N02 / COMP-R05 | "Up to ₹X" | UNKNOWN | COMP_UPPER_BOUND_ONLY | Y — fixes audit C3 |
| COMP-R06 | Undisclosed | UNKNOWN | COMP_UNDISCLOSED | Y (reaffirms OR-03b) |
| COMP-R07 | Variable / unclear / non-numeric | UNKNOWN | COMP_NON_NUMERIC | Y |
| COMP-R08 | Only equity / bonus / commission / sign-on | UNKNOWN | COMP_NON_BASE_ONLY | Y |
| COMP-R09 | India CTC: stored as `compensation_type = CTC`, never silently treated as base | normalization | — | Y (comparison: OI-007) |
| COMP-R10 | India-specific band present → use it | selection | — | Y |
| COMP-R11 | Foreign posting, location-adjusted pay, no India band | UNKNOWN | COMP_LOCATION_ADJUSTED_NO_INDIA_BAND | Y |
| COMP-R12 | Foreign base converted with a dated weekly FX snapshot, then R01–R04 apply | defer | — | **N — R2 / OI-002, OI-030** |
| COMP-R13 | Non-annual figure without a stated annualisation basis | UNKNOWN | COMP_NOT_ANNUALIZABLE | Carried (OQ-02), OI-035 |

**While COMP-R12 is unconfirmed or no FX source exists,** non-INR figures stay UNKNOWN, which is the current v0.1 behaviour (COMP-R7 of v0.1). **No live FX fetching is designed into any phase before P1**, and P1 needs OI-030 answered.

### 4.5 Employment type (OR-19)

| Rule | Condition | Verdict | Flag |
|---|---|---|---|
| EMP-R01 | Permanent direct employment | PASS | — |
| EMP-R02 | Plain full-time | PASS | — |
| EMP-R03 | Contract | FAIL | — (unstated duration: OI-021) |
| EMP-R04 | Contract-to-hire | FAIL | — |
| EMP-R05 | Temporary | FAIL | — |
| EMP-R06 | Freelance | FAIL | — |
| EMP-R07 | Part-time | FAIL | — |
| EMP-R08 | Internship | FAIL | — |
| EMP-R09 | Short-term contract (< `short_term_contract_months`, default 6, configurable) | FAIL | — |
| EMP-R10 | Long-term direct-company contract | UNKNOWN | LONG_TERM_DIRECT_CONTRACT |
| EMP-R11 | Mixed wording ("Full-Time / Contractual") | UNKNOWN | EMPLOYMENT_MIXED |
| EMP-R12 | Unstated | UNKNOWN | EMPLOYMENT_UNSTATED |

### 4.6 Employment relationship: EOR, contractor, placement (OR-20; OR-26 pending)

EOR is **not** staffing. The two are never collapsed into one category.

| Rule | Condition | Verdict | Flag | Confirmed |
|---|---|---|---|---|
| REL-R01 | Direct employment by the hiring company | PASS | — | Y |
| EOR-R01 | Permanent employment in India through a genuine EOR, working for the hiring company | UNKNOWN | EOR | **N — R1 / OI-001** |
| REL-R02 … R05 | Independent contractor · B2B · invoice-based · hourly contractor | FAIL | — | Y |
| REL-R06 | Staffing agency hires and places the candidate at another client | FAIL | — | Y |
| REL-R07 | Third-party payroll / body-shopping | FAIL | — | Y |
| REL-R08 | Staffing agency employer, relationship not yet known | UNKNOWN | EMPLOYER_TYPE_REVIEW | Y |

Contractor/freelance and contract-to-hire are also FAIL under EMP-R04 and EMP-R06.

### 4.7 Employer type, a company attribute with evidence (OR-20)

| Rule | Classification | Verdict | Flag / preference |
|---|---|---|---|
| EMPR-R05 | PRODUCT / AI_NATIVE / GCC / ENGINEERING_LED | PASS | PREFERRED_* preference signal |
| EMPR-R01 | STAFFING | UNKNOWN | STAFFING |
| EMPR-R02 | CONSULTANCY | UNKNOWN | CONSULTANCY |
| EMPR-R03 | IT_SERVICES | UNKNOWN | IT_SERVICES — never failed wholesale |
| EMPR-R04 | Unknown / unclassified | UNKNOWN | EMPLOYER_UNCLASSIFIED (OI-020; non-tech direct enterprise OI-026) |
| EMPR-R06 | An owner-confirmed classification overrides an inferred one | precedence | — |

STAFFING, CONSULTANCY and IT_SERVICES stay **separate** classifications. Third-party client placement is a relationship FAIL (REL-R06), not an employer-type FAIL.

---

## 5. Relevance (OR-12, OR-13)

- **The title is a weak prior; the JD is the primary evidence** (RELV-R01, RELV-R02). No job is rejected because its title does not match.
- **Title tiers:**
  - Tier 1: the primary target family. The full list is in the draft `title_families`.
  - Tier 2: adjacent AI engineering (ML/NLP/MLOps/ML-platform, LLM/AI application, AI software/backend/integration/product engineer, AI developer, intelligent automation, Data/AI, ML infrastructure; AI Solutions Architect only when hands-on).
  - Tier 3: any title whose JD shows substantial AI-engineering work.
  - None of Tier 2 or Tier 3 is automatically rejected.
- **Capability clusters:** A AI application · B retrieval/knowledge · C evaluation/reliability · D AI infrastructure · E agentic / AI-SDLC · F governance/trust.
- **Labels:** STRONG / MODERATE / WEAK. Each label must cite quoted spans. Generic phrases ("experience with AI tools") alone cannot produce STRONG or MODERATE (RELV-R04).
- **AI Quality vs traditional QA (RELV-R05):**
  - LLM/RAG/agent evaluation, hallucination/groundedness work and AI observability are in the target universe.
  - Selenium/Cypress/Playwright-only, manual, regression-execution, UI, mobile, ETL-only and generic test-engineering roles are generally WEAK.
  - **This is never an eligibility FAIL** (RELV-R06).
- **Evaluator output:** `relevance_label`, `evidence_spans`, `capability_clusters`, `title_signal`, `experience_signal`, `confidence`, `evaluator_version`, and where an LLM is used `model_id`, `prompt_version`, `content_hash`.
- **LLM output is evidence extraction or classification only**, never an opaque verdict (RELV-R07).
- **Experience (EXP-R01…R06):**
  - 2–3 years, exactly 3, or "3+" → DIRECT.
  - 4–6 → STRETCH.
  - 7+ → STRETCH.
  - Unspecified → UNKNOWN_FIT.
  - REASONABLE is undefined (OI-016).
  - STRETCH sets `EXPERIENCE_STRETCH`, which routes to REVIEW. It is **never** a FAIL.
- **Seniority (SEN-R01):** Senior / Lead / Staff / Principal / Architect are recorded as signals only. A Staff AI Engineer with a strong RAG/agent/evaluation JD lands in **REVIEW**, never PARKED or EXCLUDED on seniority grounds (golden case G082).

---

## 6. Preference (PREF-R01, PREF-R02)

| Attribute | Values |
|---|---|
| `compensation_band` | BELOW_TARGET_BAND · IN_TARGET_BAND · ABOVE_TARGET_BAND · UNKNOWN · NOT_APPLICABLE (compensation FAIL) |
| `employer_preference` | PREFERRED_PRODUCT · PREFERRED_AI_NATIVE · PREFERRED_GCC · PREFERRED_ENGINEERING_LED · NEUTRAL · UNKNOWN |

Preference affects the lane only through `BELOW_TARGET_BAND` (→ REVIEW), and affects ordering. It never produces FAIL.

---

## 7. Lanes, capacity and ordering (OR-22; OR-28, OR-29 pending)

Lane derivation is deterministic, first match wins:

1. **LANE-R01** Canonical duplicate → SUPPRESSED_DUPLICATE.
2. **LANE-R02** Any eligibility FAIL → EXCLUDED.
3. **LANE-R03** Relevance WEAK → PARKED. Seniority, 7+ years or foreign origin never park a STRONG role.
4. **LANE-R06** Relevance NOT_ASSESSED → not ruled (OI-015).
5. **LANE-R04** STRONG or MODERATE, and at least one UNKNOWN dimension or review-routing flag → REVIEW.
6. **LANE-R05** Otherwise → SHORTLIST.

Review-routing vs informational flags are listed in the draft `flags_registry`. Unknown **never** becomes FAIL.

**Capacity (not confirmed):**
- REVIEW cap: 10 per day (OI-003).
- Overflow carries forward for up to 3 days, then low-priority items move to PARKED and appear in the weekly digest (OI-004; exemption for STRONG items: OI-010).
- SHORTLIST is uncapped.
- The cap is a parameter.

**Ordering (LANE-R09, not confirmed, OI-009).** These are ordered categorical keys, never a score. Draft default (§25 order):

1. relevance: STRONG before MODERATE;
2. newness: NEW before UPDATED before SEEN_BEFORE;
3. evidence completeness: fewer UNKNOWN eligibility dimensions first;
4. preference alignment: IN/ABOVE target band before BELOW_TARGET_BAND before UNKNOWN; PREFERRED_* employer before NEUTRAL before UNKNOWN (REMOTE vs BENGALURU_HYBRID: OI-028);
5. tie-breaker: `first_seen_at` ascending;
6. final tie-breaker: `requisition_id` ascending, which makes the order total and reproducible.

The alternative §39 order (relevance → preference → completeness → newness) is kept in the draft as `option_B_section_39`.

---

## 8. Newness, identity and replay (OR-24)

- **Newness states:** NEW / UPDATED / SEEN_BEFORE per **canonical requisition**. Stored alongside: `first_seen_at`, `last_seen_at`, `source_first_seen_at`, `date_precision`, `newness_confidence`, `source_observations`.
  - What counts as "materially changed": OI-018.
  - Enrichment vs change: OI-017.
- **One requisition, many observations.** LinkedIn, employer ATS, company site, Naukri and other boards are observations of one requisition. The **employer requisition URL is the preferred canonical URL** (NEW-R02, NEW-R03).
- **Evaluation key:** `(requisition_id, policy_version, evidence_hash)` (EVAL-R01). Replay under v0.1, v0.2 or any later version needs only stored evidence.
- **F4 fix (EVAL-R02, EVAL-R03).** The current evaluation is built from the per-dimension **richest valid evidence** across all observations. Absent or not-captured evidence never displaces present evidence. A sparse later sighting updates `last_seen_at` only. Full semantics and precedence are in `JOBOPS_V2_DATA_MODEL.md` §5. Regression cases: G109, G110.

---

## 9. Changes vs v0.1 and superseded-rule mapping

| v0.1 / historical artifact | Old rule | v0.2 replacement | Ruling |
|---|---|---|---|
| `policy/jobops-policy-0.1.0.json` threshold T | ₹20L floor, inclusive | ₹18L floor; ₹18–24L PASS + BELOW_TARGET_BAND | OR-18 supersedes OR-03a |
| same, WM-R1 | REMOTE → PASS (any remote) | GEO-R01/R02 PASS only when worldwide or India-eligible; GEO-R03/R04 FAIL region locks | OR-14 |
| same, WM-R2 | HYBRID → FAIL | GEO-R06 (Bengaluru 0–3 days PASS), R07, R08, R09, R11 | OR-15 supersedes OR-04 hybrid clause |
| same, WM-R3 | ONSITE → FAIL | GEO-R10 (Bengaluru onsite UNKNOWN), R12, R13 | OR-15 |
| same, WM-R4/R5 | AMBIGUOUS/ABSENT → UNKNOWN | GEO-R05, GEO-R16 (principle kept) | carried |
| same, COMP-R3 (OQ-01) | Straddle across ₹20L → UNKNOWN | COMP-R04 straddle across ₹18L → UNKNOWN | OR-18 supersedes OQ-01 anchor |
| same, COMP-R5 (OR-03b) | Undisclosed → UNKNOWN | COMP-R06 (unchanged) | OR-18 reaffirms OR-03b |
| same, COMP-R7/R8 (OQ-02) | Non-INR → UNKNOWN until FX configured | COMP-R12 (pending R2) | OR-27 (unruled) |
| same, `company_type.gating:false` (OR-04) | Staffing never vetoed | REL-R06/R07 placement FAIL; EMPR-R01..R03 UNKNOWN + flag | OR-20 supersedes OR-04 staffing clause |
| same, `not_evaluated` (OR-05, OR-07) | Role exclusions and contract not gated | Contract rules EMP-R03..R12. Role exclusions become **relevance** (WEAK → PARKED), never eligibility | OR-19, OR-13 |
| same, `verdicts.primary` | PASS / UNKNOWN / FAIL, two dimensions | Six eligibility dimensions + relevance/preference/newness outputs | OR-13 |
| `review/jobops-review-0.1.0.json` lanes | SHORTLIST, REVIEW, BELOW_THRESHOLD, EXCLUDED, NOT_EVALUATED, SUPPRESSED_DUPLICATE | SHORTLIST, REVIEW, PARKED, EXCLUDED, SUPPRESSED_DUPLICATE (legacy rows: OI-034) | OR-22 |
| `docs/Career_Strategy_and_Search_Preferences.md` §2, §4 | 7-year QA narrative; ₹16L last drawn; ₹20–30+ target; remote hard constraint; ≥6-month product contract OK; four QA-era buckets | Current profile (OR-11); comp (OR-18); geography (OR-14/15); employment (OR-19); titles (OR-12) | OR-11…OR-19 |
| `ingestion/linkedin-ingestion-0.1.0.json` query seeds | AI Quality / AI Test Automation / Data & AI Quality / AI Governance buckets; `remote_filter: remote` | Tier 1 family (implementation pending OI-031); OR-08 caps unchanged | OR-12, OR-23 |
| `data/resume_config.json`, `data/SCORING_GUIDE.md`, `scrapers/simple_scorer.py` | QA Lead, 7 years, ETL weights, weighted `match_score`, auto-import ≥ 75 | Replaced by relevance labels + preference attributes; no composite score | OR-11, OR-13 |
| `prompts/job_analysis.txt`, `prompts/email_generation.txt`, `data/resumes/*` | QA Lead / Test Lead positioning | Quarantined; replacement material is P4 | OR-11 |
| Earlier 2026-09-28 preferences (audit brief) | ₹20L minimum; avoid staffing; exclude 7+ and Staff/Principal | ₹18L; staffing UNKNOWN; 7+ and Staff/Principal reviewable | OR-25 (confirmation: OI-025) |

The existing v0.1 artifacts and tests (`tests/test_p0_02_gate.py`) remain correct **for v0.1** and are not edited.

---

## 10. Known conflicts and open items

All are listed in `JOBOPS_V2_OPEN_ITEMS.md`. The highest-impact ones:

- **OI-006:** ₹18–25L example vs the floor rule.
- **OI-009:** ordering §25 vs §39.
- **OI-010:** overflow parking vs "strong relevance preserves reviewability".
- **OI-013:** Bengaluru onsite UNKNOWN vs hybrid 4–5 days FAIL.
- **OI-033:** §32 "authorize" vs R5 unconfirmed.
- **OI-020:** unclassified employers keep postings out of SHORTLIST, which interacts with the REVIEW cap. Expect a large REVIEW backlog until the company registry fills.

---

## 11. Golden cases

`tests/fixtures/policy_v02_golden_cases.json` holds **112** synthetic cases.

**What they cover:**
- all 70 scenarios required by the specification;
- extra cases for aliases, other contractor forms, AI-native/GCC employers, owner override, unclassified and enterprise employers, experience bands, cross-dimension interactions, source conflict, and an unchanged re-sighting.

**Case structure:**
- Evidence is given as quoted spans that occur in `posting_text`.
- Multi-observation cases (G106–G112) list observations in sequence, with the expected evaluation after each observation.
- `depends_on_open_items` marks expectations that assume a draft recommendation.
- `OPEN:OI-nnn` marks expectations that cannot be written until the owner rules.

**Status:** nothing consumes these cases yet. P1 adds a test module that loads them and skips `OPEN:` cases. The existing test suite is untouched.

---

## 12. Phase B amendment (2026-09-29): what is now implemented and active

- **Active artifact:** `policy/jobops-policy-0.2.0.json` (`jobops-policy@0.2.0`), interpreted by `evaluation/`. The Phase A draft in `docs/architecture/drafts/` is retained as history. The v0.1 engine (`policy/gate.py`) and `policy/jobops-policy-0.1.0.json` are unchanged; the v0.1 sha256 is recorded in the v0.2 artifact (`afe05e5a…c051f`).
- **Rulings applied:** R1–R5 (OR-26 … OR-30) plus the Phase B command's explicit rules. Where Phase B differs from this Phase A text, Phase B governs:
  - Bengaluru onsite = FAIL (§4.1 GEO-R10 is superseded);
  - ₹18–25L and ₹20–30L = PASS + `COMPENSATION_REVIEW` (§4.4 COMP-R04 example superseded);
  - CTC rules COMP-C01 … C05;
  - INR monthly × 12 + `MONTHLY_ASSUMED`;
  - explicit non-Bengaluru city residence = FAIL; listed hub = UNKNOWN + `CITY_HUB_LISTED`;
  - EMEA = FAIL via the region → country membership model;
  - language FAIL only at confidence ≥ 0.95;
  - REASONABLE = ranges containing 3 and extending above it;
  - no-JD lanes (Tier 1 → REVIEW, otherwise PARKED);
  - parking of MODERATE roles with 7+ years or a Staff/Principal/Architect title;
  - newness and source-precedence rules.
- **Flag names changed from Phase A:**
  - `BELOW_TARGET_BAND` → `BELOW_TARGET`;
  - `COMP_RANGE_OVERLAPS_FLOOR` → `SALARY_RANGE_STRADDLES_FLOOR` / `CTC_RANGE_STRADDLES_FLOOR`;
  - new flags: `IN_TARGET`, `ABOVE_TARGET`, `COMPENSATION_REVIEW`, `CTC_BASIS_UNVERIFIED`, `MONTHLY_ASSUMED`, `CITY_HUB_LISTED`, `FX_RATE_UNAVAILABLE`, `EXPERIENCE_SUBSTANTIAL_MISMATCH`, `COMP_BASIS_UNSTATED`, `COMP_UNCLASSIFIED`.
- **Preference attributes:** `compensation_band` ∈ {BELOW_TARGET, IN_TARGET, ABOVE_TARGET, SPANS_TARGET, CTC_BASIS_UNVERIFIED, UNKNOWN, NOT_APPLICABLE}; `employer_preference`; `work_arrangement` ∈ {REMOTE, BENGALURU_HYBRID, OTHER, UNKNOWN}.
- **Open questions** raised by implementation (OI-036 … OI-048) and the Phase B status of every earlier OI: `JOBOPS_V2_OPEN_ITEMS.md`, "Phase B status".
