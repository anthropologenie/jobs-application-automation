# JobOps v2 — Blind Round 2 Measurement Report (P4b)

**Date:** 2026-09-30 · **Engine/policy measured:** `jobops-policy@0.2.2` at HEAD `313ec4ca7b44c329ff9cc457f4259569a10e9b72` (branch `jobops-v2-engine`) · **Phase:** measurement only. No fixes, no policy edits, no commits.

---

## A. Executive result

| Measure | Raw (0.2.2 as is) | Resolution-adjusted |
|---|---|---|
| Posting cases | 124 | 124 |
| Posting mismatches | **106 / 124 = 85.48 %** | **110 / 124 = 88.71 %** |
| Posting cases matching | 14 (+4 UNDETERMINED not scored raw) | 14 |
| Sequences | 10 | 10 |
| Sequence mismatches | **6 / 10 = 60 %** | **6 / 10 = 60 %** |
| Harness errors / exceptions | 0 | 0 |

**The 20 % stop threshold was triggered** (85.48 % > 20 %). Per §18, individual mismatches are **not** classified into ENGINE_BUG / CASE_ERROR / SPEC_AMBIGUITY / ADAPTER_LIMIT. No xfails were added and no fix pass happened. Section F gives pattern analysis only.

A clean *execution* is not a clean *validation*. The harness ran all 124 cases and 10 sequences without an exception, but the expectations largely did **not** match.

The four UNDETERMINED cases (R2-046/051/075/076) have no raw expectation, so they are not counted as raw mismatches. The 106 are mismatches among the 120 determined cases (88.3 % of determined cases). The resolution overlay (§E) scores the four UNDETERMINED cases, and all four mismatch, which gives 110.

---

## B. Fixture integrity

| Check | Value |
|---|---|
| Expected SHA-256 | `f54eb41bc805a28162e69e77495557b3647dd82e3b7c110c2987981edee421e5` |
| Before (`sha256sum` + Python `hashlib`, original `~/jobops-blind-round2/`) | `f54eb41b…ee421e5`, both methods ✅ |
| `.sha256` file content | matches ✅ |
| Scratch copy (`tests/fixtures/policy_v02_blind_round2_cases.json`) before each run | matches ✅ |
| Inside the raw runner (start and end of execution) | matches ✅ (`fixture_sha_before` / `fixture_sha_after` recorded in the raw JSON) |
| Inside the pytest run (`test_frozen_round2_fixture_hash`) | passed ✅ |
| After all work (original, both methods) | `f54eb41b…ee421e5` ✅ |
| Frozen file set | valid JSON; 124 posting cases, 10 sequences, unique IDs; `undetermined.md` lists R2-046, R2-051, R2-075, R2-076, R2-SEQ-09 ✅ |
| Original directory modified? | No. mtimes are still 13:20, and `blind_cases_round2.sha256` = `c6216987…`, `undetermined.md` = `25e21589…` |

**Independence note:** the Round-2 corpus was written earlier in the same agent session that ran this measurement. It was authored and frozen (hash above) before any repository file was opened, and it was not changed afterwards. The measurement itself is unaffected. Still, the owner should know that the author and the measurer were not separate processes.

---

## C. Policy integrity

| Policy | Before | After | Byte-identical |
|---|---|---|---|
| 0.2.0 | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` | same | ✅ |
| 0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` | same | ✅ |
| 0.2.2 | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` (= expected) | same | ✅ |

---

## D. Raw Round-2 measurement

**Command** (scratch copy `…/scratchpad/jobops-p4b-r2-20260930-134050/`):
`python3 tests/r2_run_raw.py p4b_out/r2_raw_results.json`
The raw result file has SHA-256 `e11c9f76335e11c0e6b5c6e62c66807084b1214b73223eed8066ed2d0f8280b5` and was frozen before any analysis.

**Attempt log:** attempt 1 raised a harness input-contract error in 129 items: `an OWNER_CONFIRMED classification must be decided_by='owner'`. The harness passed a different `decided_by` label. That attempt produced no engine output. It is kept as `p4b_out/r2_attempt1_harness_error.json`. The only change was the `decided_by` argument. No engine code, policy or expectation changed.

### Harness (scratch-only files)
`tests/r2_blind_harness.py`, `tests/r2_run_raw.py`, `tests/test_policy_v02_blind_round2.py`. The mapping was fixed before execution. Expected values are read from the fixture only.

| Fixture field | Engine input |
|---|---|
| `source` linkedin/naukri/other → `JOB_BOARD`; ats → `EMPLOYER_ATS` (ats + `source_detail: "company careers page"` → `COMPANY_SITE`) | `source_kind` |
| `location_text` / `work_mode_text` / `employment_text` / `compensation_text` / `jd_text` | `raw_location` / `raw_work_mode` / `raw_employment_type` / `raw_salary` / `raw_text`. These are separate fields; nothing is concatenated. |
| completeness | explicit in sequences; for posting cases, `FULL_JD` if and only if `jd_text` is non-empty |
| `employer_type_hint` | company classification with basis `OWNER_CONFIRMED`, following the fixture convention. `unclassified` → no record. `third_party_payroll` → **no record, because the schema has no such classification** (input-contract gap). |
| `fx_snapshot_age_days` | **Not representable.** The fixture gives no rate and the repository has no owner FX table (`OWNER_RULINGS_LOG.md` confirms no rate values exist). No FX row was seeded, because inventing a rate is forbidden. |
| clock | posting cases: 2026-09-30 (fixture `authored_on`); sequences: each run's `observed_on` |
| sequence `requisition_id` | one shared employer URL `https://careers.<slug>.example/jobs/<id>`, used as `source_url` for ATS/company site and `apply_url` for boards. This gives all sightings of one requisition a shared L2 identity key. `null` → no key. |
| language | no detection input exists in the fixture, so the engine's own heuristic detector is used. Round 1 supplied `jd_language`. |
| R2-SEQ-07 queue convention | after each planned day, every surfaced member gets a human `SKIP` decision, so surfaced items leave the pool (§14) |
| R2-SEQ-07 `history_note` | the stated earlier identical sighting is ingested on its stated date before day D |
| enrichment blocks (R2-SEQ-06) | no engine input exists; ignored, so the observation is otherwise identical |
| Projection | Round-1 convention: `employment_type` = worst of the engine's `employment_type` and `employment_relationship`; `employer_type` is worsened to FAIL on REL-R06/R07 |

### Raw totals by coverage area (mismatching / determined cases tagged with that area)

| Area | A work mode | B compensation | C employment | D other |
|---|---|---|---|---|
| Mismatching | 38 / 43 | 36 / 36 | 17 / 17 | 32 / 41 |

The 14 fully matching determined cases are R2-001, 002, 007, 009, 033, 100, 101, 102, 103, 104, 107, 108, 109, 110.

### Mismatch fields (raw, 120 determined cases)

| Field | Mismatches | Dominant pair (expected → actual) |
|---|---|---|
| relevance | 99 | STRONG → WEAK ×72; STRONG → MODERATE ×26 |
| lane | 67 | SHORTLIST → PARKED ×24; REVIEW → PARKED ×20; SHORTLIST → REVIEW ×11 |
| language | 59 | PASS → UNKNOWN ×57 |
| geography | 17 | PASS → UNKNOWN ×12; FAIL → UNKNOWN ×3 |
| compensation | 9 | PASS → UNKNOWN ×7 |
| flags (must have / must not have) | 10 | — |
| employment_type | 5 | — |
| employer_type | 1 | — |

---

## E. Resolution-adjusted measurement

Overlay file (scratch only): `tests/fixtures/policy_v02_blind_round2_owner_resolutions.json`. It contains only the five owner resolutions and is applied to the frozen raw result. It does not change the fixture, the policy or the engine.

| Item | Owner resolution | Raw engine result | Adjusted |
|---|---|---|---|
| R2-046 | `BELOW_TARGET` = review flag → REVIEW | comp PASS + `BELOW_TARGET` + `CTC_BASIS_UNVERIFIED`; language UNKNOWN (LANG-R05); relevance WEAK → **PARKED** | ❌ lane (because of relevance/language, not the flag) |
| R2-051 | `COMPENSATION_REVIEW` = review flag → REVIEW | comp PASS + `COMPENSATION_REVIEW`; relevance WEAK → **PARKED** | ❌ lane |
| R2-075 | EOR → UNKNOWN + EOR → REVIEW | employment UNKNOWN (EOR-R01) + `EOR` ✅; comp UNKNOWN (`COMP_PERIOD_UNSTATED`, no FX row); relevance WEAK → **PARKED** | ❌ lane |
| R2-076 | EOR in the JD counts; structured Full-time does not override | employment UNKNOWN (EOR-R01) + `EOR` ✅; relevance WEAK → **PARKED** | ❌ lane |
| R2-SEQ-09, step 2 | SEARCH_ONLY → FULL_JD on the same source = SEEN_BEFORE | newness **SEEN_BEFORE** ✅ | newness matches. The sequence still mismatches on geography and lane (see J). |

**Adjusted totals:** posting mismatches 110 / 124 = 88.71 %; sequences 6 / 10 = 60 %.

**Policy-state check:** 0.2.2 already classifies `BELOW_TARGET`, `COMPENSATION_REVIEW` and `EOR` as `review_routing`, and the engine emits them where the owner expects. There is **no implementation/policy-state discrepancy** on these three flags. The four remaining adjusted mismatches come from the relevance and language patterns below.

---

## F. Mismatch classification — not produced (stop threshold triggered)

Per §18, the classes are not assigned. The following is pattern analysis only.

### Concentration
Mismatches span all four coverage areas, so they are not confined to one area. However, **73 of the 106 mismatching cases differ only in relevance, language and/or the resulting lane**; their five eligibility verdicts and asserted flags all match. Two patterns (P1, P2) therefore account for most of the raw rate. 35 cases have at least one eligibility-verdict or flag mismatch (P3–P7).

### P1 — Relevance rated lower than the corpus expects (99 cases)
- **Mechanism:** `relevance/labeller.py` and policy `relevance.thresholds`. STRONG requires at least 3 distinct AI-specific lexicon terms spanning at least 2 clusters; MODERATE requires at least 2. Many corpus JDs describe AI work in wording the lexicon does not contain, such as "evals", "SLOs for our LLM … service", "golden sets", "guardrails" and "agents".
- **Examples:**
  - R2-013 *AI Reliability Engineer*: one term ("LLM") → WEAK.
  - R2-029 *AI Engineer*: one term → WEAK.
  - R2-001: seven terms across three clusters → STRONG ✅.
- **Lane effect:** 24 SHORTLIST → PARKED and 20 REVIEW → PARKED. The engine parks WEAK relevance, so relevant roles are demoted, not excluded.
- **R2-SEQ-07:** all seven MODERATE items evaluated WEAK → PARKED, so the designed ordering and cap test could not run as written.

### P2 — Language UNKNOWN on English JDs (64 cases at LANG-R05; 57 expected PASS)
- **Mechanism:** with no external `language_detection` input, the engine's heuristic detector (`evaluation/extract.py::_language`) reports `UNDETERMINED`, which LANG-R05 turns into `UNKNOWN` + `LANGUAGE_UNCERTAIN` (review-routing).
- **Pattern:** this happens on 64 of 124 English JDs. Round 1 supplied detection results through fixture fields; the Round-2 fixture has none.

### P3 — Bengaluru office-day wording not recognised (GEO-R08 `HYBRID_DAYS_UNSPECIFIED`)
Stated office days were read as unspecified. Examples:
- R2-005 "Tuesdays and Thursdays"
- R2-010 "three days in a week"
- R2-013 "Mon, Wed and Thu"
- R2-016 alternate days
- R2-017 "One anchor day per week"
- R2-018 "8 days a month"
- R2-115 "two days per week"
- the sequences: SEQ-05 "Tuesdays and Thursdays", SEQ-08 "Two office days a week" / "Office twice a week", SEQ-09 "Monday and Thursday"

Expected FAILs were also returned UNKNOWN: R2-019 "18 days in a month" and R2-020 "Monday through Thursday". Direction: REVIEW noise, plus FAIL → REVIEW/PARKED.

### P4 — Work-mode conflict detection (GEO-R25)
- **`WORK_MODE_CONFLICT` raised where the expectation is none or FAIL:**
  - R2-008: a negated statement, "not a hybrid role", raised the flag.
  - R2-012 and R2-021: consistent Hybrid + JD wording raised it.
  - R2-022: "Friday is our WFH day" was expected FAIL and came out UNKNOWN.
- **The opposite case:** R2-025, where the location says Remote, India and the JD says "five days a week" from a Chennai office. It was expected UNKNOWN + `WORK_MODE_CONFLICT` and got **PASS / SHORTLIST**. This is the only false SHORTLIST in the run.

### P5 — "Contract" wording read as contract employment (EMP-R03 FAIL)
This is the **most severe direction, because relevant roles are wrongly EXCLUDED.**
- R2-083 is a permanent role whose JD says "contract testing", "OpenAPI contracts", "smart contract" and "vendor contracts".
- R2-072 is a direct 24-month fixed-term role.
- R2-073 is direct employment with no duration (Addendum D).
- R2-SEQ-04 is "Full Time, Permanent" with a JD mentioning a "contract-review assistant".

All four came out `employment_type FAIL` → **EXCLUDED**.

### P6 — Compensation parsing
- **R2-066:** a US band alongside "India: ₹42–55 LPA base" → **FAIL (COMP-R01) → EXCLUDED**. This is a false EXCLUDED.
- **R2-040 (fixed + variable):** see I.
- R2-037, a table-style "Fixed base … INR 26,00,000 / Annual CTC … INR 33,50,000" → UNKNOWN (`COMP_PERIOD_UNSTATED`).
- R2-041, "₹27L fixed + up to 15% bonus" → UNKNOWN (`SALARY_RANGE_STRADDLES_FLOOR`).
- R2-068, no salary but "25 lakh users" in the JD → PASS + `IN_TARGET` (COMP-R02). The expectation was UNKNOWN.
- **FX cases** (R2-023, 024, 060–064, 075): no FX row exists, so the engine returns `FX_RATE_UNAVAILABLE`/UNKNOWN. The expected `FX_STALE` or PASS cannot be produced under the current input. This matches the ADAPTER_LIMIT description in §13, but it is not formally classified here because of the stop rule.

### P7 — Geography, language and employer outliers
- **R2-023:** "Remote — Canada" came out geography FAIL (GEO-R03) → **EXCLUDED**; the corpus expected UNKNOWN.
- **R2-090:** "Business-level Japanese (JLPT N2 or above) is mandatory" came out language PASS (expected FAIL). Because relevance is WEAK it went to PARKED, not SHORTLIST.
- **R2-094:** a fully German JD came out UNKNOWN (LANG-R05); the corpus expected FAIL.
- **R2-122:** the `third_party_payroll` hint cannot be represented (input-contract gap) → UNKNOWN + `EMPLOYER_UNCLASSIFIED`; the corpus expected FAIL.
- **R2-047 and R2-111:** a staffing employer adds REL-R08 `EMPLOYER_TYPE_REVIEW`, which the Round-1 projection counts as employment UNKNOWN.

### Direction summary (raw lanes)
| Direction | Count | Cases |
|---|---|---|
| False EXCLUDED | 5 postings + 1 sequence | R2-023, **R2-066**, **R2-072**, **R2-073**, **R2-083**; R2-SEQ-04 |
| False SHORTLIST | 1 | R2-025 |
| Demoted to PARKED | 48 (24 from SHORTLIST, 20 from REVIEW, 4 expected EXCLUDED) | mostly P1 |
| SHORTLIST → REVIEW (REVIEW noise) | 11 | mostly P2/P3 |

---

## G. ENGINE_BUG groups — not produced

The stop rule forbids classifying individual mismatches, so there are no ENGINE_BUG groups. The modules the patterns trace to, for the owner's orientation only:

| Pattern | Module |
|---|---|
| P1 | `relevance/labeller.py`, `relevance` lexicon |
| P2 | `evaluation/extract.py::_language` |
| P3 and P4 | geography extraction and `lexicon.office_days` / `hybrid_semantics`, rules GEO-R08 and GEO-R25 |
| P5 | `lexicon.employment` / `employment_cue_exclusions`, rule EMP-R03 |
| P6 | `evaluation/compensation.py` |

---

## H. Flag classification (policy 0.2.2, read-only)

Every flag that policy 0.2.2 defines is classified; none is unclassified. "—" means the flag is set outside the rule tables (by identity, newness, relevance or the lexicon).

| Flag | Class | Rule(s) that set it |
|---|---|---|
| `ABOVE_TARGET` | informational | COMP-R17 |
| `BELOW_TARGET` | review_routing | COMP-C02, COMP-C06, COMP-R03 |
| `CITY_HUB_LISTED` | review_routing | GEO-R22 |
| `COMPENSATION_REVIEW` | review_routing | COMP-C03, COMP-R15 |
| `COMP_BASIS_UNSTATED` | informational | — |
| `COMP_LOCATION_ADJUSTED_NO_INDIA_BAND` | review_routing | COMP-R11 |
| `COMP_NON_BASE_ONLY` | review_routing | COMP-R08 |
| `COMP_NON_NUMERIC` | review_routing | COMP-R07 |
| `COMP_NOT_ANNUALIZABLE` | review_routing | COMP-R13 |
| `COMP_PERIOD_UNSTATED` | review_routing | COMP-R16 |
| `COMP_UNCLASSIFIED` | review_routing | COMP-R99 |
| `COMP_UNDISCLOSED` | review_routing | COMP-R06 |
| `COMP_UPPER_BOUND_ONLY` | review_routing | COMP-R05 |
| `CONSULTANCY` | review_routing | EMPR-R02 |
| `CONTRACT_DURATION_UNSTATED` | review_routing | EMP-R14 |
| `CTC_BASIS_UNVERIFIED` | informational | COMP-C01, C02, C03, C04, C06 |
| `CTC_RANGE_STRADDLES_FLOOR` | review_routing | COMP-C05 |
| `EMPLOYER_TYPE_REVIEW` | review_routing | REL-R08 |
| `EMPLOYER_UNCLASSIFIED` | review_routing | EMPR-R04 |
| `EMPLOYMENT_MIXED` | review_routing | EMP-R11 |
| `EMPLOYMENT_UNSTATED` | review_routing | EMP-R12 |
| `EOR` | review_routing | EOR-R01 |
| `EXPERIENCE_STRETCH` | review_routing | — |
| `EXPERIENCE_SUBSTANTIAL_MISMATCH` | informational | — |
| `FX_RATE_UNAVAILABLE` | review_routing | COMP-R14 |
| `FX_STALE` | review_routing | COMP-R19 |
| `GEO_REGION_AMBIGUOUS` | review_routing | GEO-R05 |
| `HYBRID_DAYS_UNSPECIFIED` | review_routing | GEO-R08 |
| `HYBRID_FLEXIBLE` | review_routing | GEO-R09 |
| `IDENTITY_UNCERTAIN` | review_routing | — |
| `IN_TARGET` | informational | COMP-R02, COMP-R18 |
| `IT_SERVICES` | review_routing | EMPR-R03 |
| `LANGUAGE_PREFERENCE` | informational | LANG-R03 |
| `LANGUAGE_UNCERTAIN` | review_routing | LANG-R05, LANG-R06 |
| `LONG_TERM_DIRECT_CONTRACT` | review_routing | EMP-R10 |
| `MONTHLY_ASSUMED` | informational | — |
| `SALARY_RANGE_STRADDLES_FLOOR` | review_routing | COMP-R04 |
| `SENIORITY_SENIOR` / `_LEAD` / `_STAFF` / `_PRINCIPAL` / `_ARCHITECT` | informational | — |
| `SOURCE_CONFLICT` | review_routing | — |
| `STAFFING` | review_routing | EMPR-R01 |
| `TIMEZONE_OVERLAP_US` / `_UK` / `_EU` / `_APAC` | informational | — |
| `WORK_ARRANGEMENT_ABSENT` | review_routing | GEO-R16 |
| `WORK_ARRANGEMENT_AMBIGUOUS` | review_routing | GEO-R19 |
| `WORK_LOCATION_AMBIGUOUS` | review_routing | GEO-R23 |
| `WORK_MODE_CONFLICT` | review_routing | GEO-R25 |

The table does not rewrite the fixture. It records how the implementation currently classifies each flag.

---

## I. Owner questions

1. **Fixed + variable (R2-040).** The engine reads "Fixed: ₹15 LPA + Variable: ₹5 LPA (Total CTC ₹20 LPA)" as base ₹15L → **compensation FAIL (COMP-R01) → EXCLUDED**, which matches the author's reading. The ruling that fixed pay equals base is still not written in the rulings sheet. Should it be recorded, yes or no?
2. **`EXPERIENCE_STRETCH` is review-routing in 0.2.2.** The Round-2 rulings say experience is "never FAIL" but don't say whether STRETCH should route to REVIEW. Should it, yes or no?
3. **Language detection input.** Should the evaluation of an English-only JD depend on an external detector result, when the built-in heuristic caps confidence at 0.9, below the 0.95 threshold? (Input-contract question, P2.)
4. **Third-party payroll as an owner classification.** The schema has no `THIRD_PARTY_PAYROLL` employer classification, so an owner cannot express the corpus's `third_party_payroll` hint (R2-122). Should one be added, yes or no?
5. **FX input for holdouts.** Blind fixtures cannot exercise FX without owner rates. Should blind corpora carry a rate and snapshot date (as Round 1 did), yes or no?
6. **Staffing and REL-R08.** Should `EMPLOYER_TYPE_REVIEW` (set on the employment-relationship dimension) count toward the blind "employment_type" projection? The Round-1 projection counts it, which produces the R2-047 and R2-111 mismatches.

Not an open question: no policy version mismatch. 0.2.2 is exactly the expected hash.

---

## J. Sequence findings (raw)

| Sequence | Result | Detail |
|---|---|---|
| **R2-SEQ-01** F4, PASS retained | ❌ | Verdict stays PASS and newness is SEEN_BEFORE ✅. But the board SEARCH_ONLY re-observation raised `SOURCE_CONFLICT`, which moved the lane SHORTLIST → **REVIEW**. The expectation was that the search-only sighting would not affect the lane. |
| R2-SEQ-02 F4, FAIL retained | ✅ | FAIL / EXCLUDED retained, SEEN_BEFORE. `SOURCE_CONFLICT` was also raised, which was not asserted. |
| R2-SEQ-03 cross-source UPDATED | ✅ | UPDATED + `SOURCE_CONFLICT` → REVIEW |
| **R2-SEQ-04** cross-source unchanged | ❌ | Newness NEW → SEEN_BEFORE ✅ and no `SOURCE_CONFLICT` ✅. However, "contract-review assistant" in the JD caused employment FAIL (EMP-R03) → EXCLUDED at both steps (P5). |
| **R2-SEQ-05** Addendum C same run | ❌ | **NEW + `SOURCE_CONFLICT` → REVIEW ✅**, so the Addendum C behaviour holds. Geography came out UNKNOWN (`HYBRID_DAYS_UNSPECIFIED`, "Tuesdays and Thursdays"; P3) where PASS was expected. |
| R2-SEQ-06 enrichment | ✅ | SEEN_BEFORE, SHORTLIST unchanged |
| **R2-SEQ-07** REVIEW cap and carry | ❌ | All seven MODERATE items were evaluated WEAK → PARKED at intake (P1), so only 5 STRONG items plus 1 extra were surfaced on D. The extra was `req_0000004`, a separate requisition created by the S4 history sighting, because fixture items carry no identity key (harness representation limit). The designed ordering, cap and M6/M7 carry checks could not run. **STRONG exemption ✅:** S13 overflowed D+1 through D+4 and was never parked. |
| **R2-SEQ-08** identity grouping | ❌ | **Grouping ✅:** 2 requisitions retained, both `IDENTITY_UNCERTAIN`, one grouped card, one cap slot. Geography came out UNKNOWN on both ("Two office days a week" / "Office twice a week"; P3). |
| **R2-SEQ-09** richer observation | ❌ | Step 1 matches (REVIEW, NOT_ASSESSED, NEW). In step 2 relevance becomes STRONG ✅ and newness is SEEN_BEFORE, which matches the owner resolution. Geography stayed UNKNOWN ("Monday and Thursday"; P3), so the lane is REVIEW, not SHORTLIST. |
| R2-SEQ-10 lower-authority stale conflict | ✅ | ATS value kept (PASS), SEEN_BEFORE + `SOURCE_CONFLICT` → REVIEW |

---

## K. Full-suite result (scratch copy)

Command: `python3 -m pytest tests -q --tb=no -p no:cacheprovider --junitxml=p4b_out/junit_full.xml`.

The first full run produced 118 errors and 7 failures across the P0-06, P0-07, P0-08 and P0-10 modules, all "unable to open database file". The scratch copy intentionally excluded databases. A byte copy of `data/jobs-tracker.db` was then made as §1.3 permits; the file was copied without being opened, and the original's hash `bf17ebb1…3285` is unchanged. The suite was then re-run.

| Module group | Passed | Failed | xfailed | xpassed | skipped | errors |
|---|---|---|---|---|---|---|
| Original / P0 tests (p0_02, 06, 07, 08, 10) | 363 | 0 | 0 | 0 | 0 | 0 |
| 0.2.0 golden (`test_policy_v02_golden`) | 642 | 0 | 0 | 0 | 0 | 0 |
| 0.2.1 (`test_p1a_policy_021`) | 50 | 0 | 0 | 0 | 0 | 0 |
| 0.2.2 (`test_p3_policy_022`) | 27 | 0 | 0 | 0 | 0 | 0 |
| v0.2 unit and support tests (engine, relevance, lanes, identity, F4, guardrails, migrations, tool) | 107 | 0 | 0 | 0 | 0 | 0 |
| Round-1 blind (`test_policy_v02_blind`) | 158 | 0 | 0 | 0 | 0 | 0 |
| **Pre-existing suite total** | **1347** | **0** | 0 | 0 | 0 | 0 |
| **Round-2 blind (raw, no xfails)** | 20 | **112** | 0 | 0 | 0 | 0 |
| Grand total | 1367 | 112 | 0 | 0 | 0 | 0 |

The 20 Round-2 passes are 2 integrity tests + 14 cases + 4 sequences. The 4 UNDETERMINED cases are not parametrised. The shell-script tests (`tests/*.sh`) are not part of the pytest suite and were not run.

---

## L. Git integrity (original repository)

**Before**
```
git status --short   → (empty)
HEAD                 → 313ec4ca7b44c329ff9cc457f4259569a10e9b72
branch               → jobops-v2-engine
```
**After all measurement work** (captured before this report was written)
```
git status --short   → (empty)
HEAD                 → 313ec4ca7b44c329ff9cc457f4259569a10e9b72
branch               → jobops-v2-engine
```
No git command that changes the index, history, branches, tags or stash was run. All execution happened in a filesystem copy (`rsync`, excluding `.git`, `.env`, `data/n8n` and DB files). **The only repository change made by P4b is this untracked report file.**

### Proposed rulings (not written to the canonical log)
- **OI-050 = NO (Addendum C):** board and ATS sightings that conflict on first observation in the same run → `NEW + SOURCE_CONFLICT`, not UPDATED. The engine's current behaviour matches (R2-SEQ-05).
- **OI-051 = YES (Addendum D):** a direct-company contract with direct-employment evidence and no stated duration → `UNKNOWN + CONTRACT_DURATION_UNSTATED`. A plain `Contract` without direct evidence and without duration stays FAIL. The engine currently returns FAIL (EMP-R03) for R2-073.

### Artifacts (scratch, not in the repository)
`/tmp/claude-1000/-home-katte-projects-jobs-application-automation/b8cb3e08-40f6-46a8-b26d-ff517e616259/scratchpad/jobops-p4b-r2-20260930-134050/`:
- `p4b_out/r2_raw_results.json` (sha `e11c9f76…80b5`)
- `p4b_out/r2_attempt1_harness_error.json`
- `p4b_out/pattern_analysis.txt`
- `p4b_out/resolution_adjusted.txt`
- `p4b_out/flag_table.md`
- `p4b_out/junit_full.xml`
- the harness files listed in §D
- the overlay file

The scratch directory is session-temporary.
