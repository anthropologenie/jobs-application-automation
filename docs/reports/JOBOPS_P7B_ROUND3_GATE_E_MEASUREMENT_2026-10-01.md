# JobOps v2 — P7b Round 3 Gate E Measurement (2026-10-01)

These were measurement and governance passes only. No engine, policy, frozen fixture, test or Git state was changed.

This report has two parts, and they must not be merged:

- **Part A, initial frozen-corpus measurement.** Scored against the frozen `expected` values exactly as committed.
- **Part B, corrected measurement.** Scored against the frozen corpus with the author expected-output correction overlay applied in memory, and OR-88 governing S-08. **Part B is the authoritative result.**

## Executive result (corrected measurement, Part B)

```text
Gate E: FAIL
```

- **Geography: 97/107 = 90.65 %**, below the 95 % threshold.
- **Other dimensions:**

  | Dimension | Accuracy |
  |---|---:|
  | Compensation | 99.07 % |
  | Employment | 99.07 % |
  | Employer | 100 % |
  | Language | 100 % |

- **False EXCLUDED: 1 total, 1 unexplained (R3-005).** The 0.2.4 engine does not recognise "applicants resident in India are eligible" as explicit India eligibility. Classified ENGINE_ERROR.
- **False SHORTLIST: 0.**
- **Sequences: 6 PASS, 2 FAIL** (S-02 and S-08). Under OR-88, S-08 is reclassified from SPEC_AMBIGUITY to ENGINE_ERROR.
- **Genuine engine mismatches: 15**, made up of 12 dimension mismatches, 1 flag-only mismatch and 2 sequences.
- **Corpus defects: 11**, all authoring errors. These do not constitute engine errors.

## Frozen inputs

| Item | Value | Status |
|---|---|---|
| Commit | `5f1defc00323d7c9d906f92235108e700810d680` | HEAD = `round3-frozen` = `origin/jobops-v2-engine` ✔ |
| Tag | `round3-frozen` → `5f1defc` | ✔ |
| Policy version | `jobops-policy@0.2.4` | ✔ |
| Policy hash | `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136` | ✔ before and after both runs |
| Corpus | `data/fixtures/round3/blind_cases_round3.json` | byte-identical, unmodified |
| Corpus SHA-256 | `25aef0e0c0096d31231cc8ea96ea8c4796ba981c0160daa148ebeecad7c639cb` | `sha256sum -c` → `OK`, before and after both runs |
| Posting cases / sequences | 107 / 8 | ✔ |
| Overlay path | `data/fixtures/round3/blind_round3_expected_output_corrections.json` | owner-supplied, untracked, not modified by this pass |
| Overlay status | `kind`: "author expected-output corrections (authoring defect)". `applies_to_hash` = frozen corpus SHA. 11 corrections. | **validated** (see below) |
| Rulings | OR-88 and Addendum H appended to `OWNER_RULINGS_LOG.md` | append-only: 40 lines added, 0 removed |

### Overlay validation

| Check | Result |
|---|---|
| `applies_to_hash` equals the frozen corpus SHA | ✔ |
| Labelled "author expected-output corrections" | ✔ |
| Overlay IDs are exactly R3-004, 007, 011, 012, 014, 017, 018, 025, 026, 027, 029 | ✔ (11) |
| Every ID unique and present in the frozen corpus | ✔ |
| Each correction sets only `geography = FAIL` and `excluded = true` (besides `id` and `basis`) | ✔ |
| Original frozen value for each was `geography = PASS`, `excluded = false` | ✔ |
| No other dimension changed, and no other corrected case already has a FAIL dimension, so `excluded = true` is fully explained by geography | ✔ |
| Each `basis` quotes the case's own `tests` label and `rationale` verbatim | ✔ |
| Posting text, tests and rationales untouched | ✔ (the overlay is applied to an in-memory copy; corpus file SHA unchanged) |

## Method (both parts)

- **Engine and storage.** `EvaluationService.ingest` / `current_evaluation` and `evaluation.queue.plan_day`, run on fresh in-memory SQLite (`tests/v02_support.fresh_service`).
- **Adapter.** The accepted P4b/P5 adapter from `tests/r2_blind_harness.py` (`obs_fields`, `prepare`, `project(..., "p5")`), imported unchanged.
- **Round-3 additions.** Fixed before the first run and identical in both parts:
  - The posting-case clock is `evaluation_date`, falling back to `posted_date`.
  - Each case's own `fx_table` is loaded through `add_fx_rate`.
  - A sequence run is `<seq>-<observed_on>`.
  - The S-06 enrichment is applied as an owner classification.
  - In S-08 the owner SKIPs every shown item.
- **Part B overlay.** The overlay updates `expected` on an in-memory copy after the corpus SHA is checked. Nothing else differs from Part A.
- **Isolation.** The measurement script and raw outputs live in the session scratchpad, outside the repository. Sockets were refused, and no LLM was used.

---

# Part A — Initial frozen-corpus measurement (superseded by Part B)

Scored against the frozen `expected` values literally. This part is kept for the record. Its geography figure **must not be carried forward**: it includes the 11 incorrect corpus expectations.

| Dimension | Correct | Total | Accuracy | >=95% |
|---|---:|---:|---:|---|
| Geography | 89 | 107 | 83.18 % | no |
| Compensation | 106 | 107 | 99.07 % | yes |
| Employment | 106 | 107 | 99.07 % | yes |
| Employer | 106 | 106 | 100.00 % | yes |
| Language | 105 | 105 | 100.00 % | yes |

**False EXCLUDED: 9 total, 1 unexplained.**

- 8 cases (R3-004, 007, 011, 017, 025, 026, 027, 029) were explained by the corpus authoring defect: the engine's FAIL matched each case's own tests and rationale.
- 1 case, R3-005, was unexplained.

**Other Part A results:**

- False SHORTLIST: 0.
- Sequences: 6 PASS, 2 FAIL.
  - S-02: ENGINE_ERROR.
  - S-08: classified SPEC_AMBIGUITY pending an owner ruling, since resolved by OR-88.
- 20 % stop rule: 20 of 107 cases had a Gate E mismatch (18.69 %), so it did not trigger.
- Part A determination: Gate E FAIL.

---

# Part B — Corrected measurement (frozen corpus + author-correction overlay + OR-88)

## Gate E table

| Dimension | Correct | Total | Accuracy | >=95% | Expected FAIL / UNKNOWN / PASS | Mismatches |
|---|---:|---:|---:|---|---|---:|
| Geography | 97 | 107 | 90.65 % | **NO** | 11 / 8 / 88 | 10 |
| Compensation | 106 | 107 | 99.07 % | yes | 6 / 8 / 93 | 1 |
| Employment | 106 | 107 | 99.07 % | yes | 9 / 7 / 91 | 1 |
| Employer | 106 | 106 | 100.00 % | yes | 1 / 2 / 103 | 0 |
| Language | 105 | 105 | 100.00 % | yes | 3 / 2 / 100 | 0 |

**Notes on the counts:**

- **Employer total (106):** R3-095 is excluded because the corpus deliberately omits its verdict (`EMPLOYER_UNCLASSIFIED`).
- **Language total (105):** R3-102 and R3-103 are excluded because they are no-JD records.
- **Employment** is the projected employment_type, with employment_relationship folded in as p5 specifies.

### 20 % stop rule

Corpus defects are not counted as engine mismatches. 12 of 107 posting cases have a genuine Gate E dimension mismatch (11.21 %). Adding the flag-only R3-087 gives 13 of 107 (12.15 %). Both are below 20 %, so the stop rule is **not triggered**.

## Corpus defects (11 authoring errors)

**These do not constitute engine errors.**

In each case below, the frozen `expected` object carries geography PASS and `excluded = false`. The case's own `tests` label and `rationale` specify FAIL, and the intended FAIL was not copied into `expected`. The overlay supplies `geography = FAIL` and `excluded = true`. This is recorded in Addendum H of `OWNER_RULINGS_LOG.md`.

| Case | Case's own test label | Engine 0.2.4 (rule) | Engine vs corrected expectation |
|---|---|---|---|
| R3-004 | Region lock that excludes India: FAIL | FAIL (GEO-R03) | match |
| R3-007 | 'Remote – EMEA' is FAIL because India is outside EMEA | FAIL (GEO-R03) | match |
| R3-011 | Statements welcoming other countries do not count as India eligibility (LATAM lock stays FAIL) | FAIL (GEO-R03) | match |
| R3-012 | Work authorization required elsewhere: FAIL | UNKNOWN (GEO-R05) | **mismatch: genuine engine gap, listed below** |
| R3-014 | Region lock that excludes India (US) | UNKNOWN (GEO-R05) | **mismatch: genuine engine gap, listed below** |
| R3-017 | Bengaluru hybrid: 4 or 5 days FAIL (Mon–Thu) | FAIL (GEO-R07) | match |
| R3-018 | Bengaluru hybrid: 4 or 5 days FAIL (five days) | UNKNOWN (GEO-R08) | **mismatch: genuine engine gap, listed below** |
| R3-025 | Bengaluru on-site: FAIL | FAIL (GEO-R10) | match |
| R3-026 | Hybrid outside Bengaluru: FAIL (Hyderabad) | FAIL (GEO-R11) | match |
| R3-027 | On-site abroad, relocation or visa roles: FAIL (Singapore) | FAIL (GEO-R14) | match |
| R3-029 | Explicit requirement to reside in a non-Bengaluru Indian city: FAIL (Chennai) | FAIL (GEO-R17) | match |

**Two distinct facts for R3-012, R3-014 and R3-018:**

1. Their frozen expectation was a corpus defect, now corrected.
2. Against the corrected FAIL expectation, the engine's UNKNOWN is a separate, genuine engine mismatch.

That engine mismatch existed under either reading, and it is a recall-safe miss: the case lands in PARKED, not SHORTLIST. These cases appear in both tables because they carry both findings. They are not double-counted in any metric.

## Genuine engine mismatches

| # | ID | Dimension / field | Expected | Actual (rule) | Evidence | Classification | Applicable ruling / rule |
|---|---|---|---|---|---|---|---|
| 1 | R3-003 | geography | PASS | UNKNOWN (GEO-R05), REVIEW | Plain "Remote". JD: "reserved for engineers who live in India". India eligibility is not recognised. | ENGINE_ERROR | OR-83 (explicit India eligibility → PASS) |
| 2 | **R3-005** | geography / excluded | PASS / false | **FAIL (GEO-R03), EXCLUDED** | "Remote – Germany". JD: "applicants resident in India are eligible for this position". The 0.2.4 implementation does not recognise this as explicit India eligibility, so the single-country lock applies. | ENGINE_ERROR | OR-79 / OR-83 (country + India eligibility → PASS) |
| 3 | R3-010 | geography | PASS | UNKNOWN (GEO-R05), PARKED | "Remote – APAC". JD: "applicants resident in India are our priority". Not recognised. | ENGINE_ERROR | OR-83 (APAC + India → PASS) |
| 4 | R3-012 | geography | FAIL (corrected) | UNKNOWN (GEO-R05), PARKED | "legally authorized to work in the country where the job is posted" is not recognised as a work-authorization lock. | ENGINE_ERROR | Work authorization elsewhere → FAIL |
| 5 | R3-014 | geography | FAIL (corrected) | UNKNOWN (GEO-R05), PARKED | "Candidates must live in the United States" is not recognised as a residence lock. | ENGINE_ERROR | Region/country lock excluding India → FAIL |
| 6 | R3-015 | geography | PASS | UNKNOWN (GEO-R08, HYBRID_DAYS_UNSPECIFIED), PARKED | "on two fixed days each week" is not parsed. | ENGINE_ERROR | Bengaluru hybrid ≤ 3 days → PASS |
| 7 | R3-018 | geography | FAIL (corrected) | UNKNOWN (GEO-R08), PARKED | "on all five working days of the week" is not parsed. | ENGINE_ERROR | Bengaluru hybrid 4–5 days → FAIL |
| 8 | R3-020 | geography | PASS | UNKNOWN (GEO-R08), PARKED | "Eleven days per month" is not normalised (≈ 2.5 per week). | ENGINE_ERROR | Monthly ÷ 4.33 normalisation |
| 9 | R3-033 | geography | PASS | UNKNOWN (GEO-R08), REVIEW | "Three days a week are spent in the Bengaluru building" is not parsed. The technical "hybrid" mention was correctly ignored. | ENGINE_ERROR | Bengaluru hybrid ≤ 3 days; Addendum C/D |
| 10 | R3-034 | geography | PASS | UNKNOWN (GEO-R08), PARKED | "three days at the Bengaluru office and two at home" is not parsed. | ENGINE_ERROR | Addendum C (JD work statement counts) |
| 11 | R3-059 | compensation | UNKNOWN | PASS (COMP-R17), PARKED | "$130,000 – $160,000 per year; pay is adjusted to the candidate's location". The 0.2.4 `location_adjusted` lexicon does not match "adjusted to the candidate's location", so the band is converted at 83.4. | ENGINE_ERROR | Location-adjusted pay, no India band → UNKNOWN (COMP-R11; OR-18 basis) |
| 12 | R3-078 | employment_type | FAIL | PASS (EMP-R02; REL-R01), EXCLUDED | "employed by our staffing partner and placed full time at one of their clients" is not detected. The lane is still correctly EXCLUDED via employer FAIL (EMPR-R08). | ENGINE_ERROR | Third-party payroll / client placement → FAIL |
| 13 | R3-087 | must_have_flags (not a dimension) | LANGUAGE_PREFERENCE | absent, SHORTLIST | "Hindi is preferred but not required" raises no flag. The language verdict PASS is correct. The flag is informational and does not route, so this is not a false SHORTLIST. | ENGINE_ERROR | OR-81 (informational flag) |
| 14 | S-02 | geography / excluded, both steps | FAIL / true | UNKNOWN / REVIEW | "on all five working days of the week" is not parsed. Same gap as R3-018. | ENGINE_ERROR | Bengaluru hybrid 4–5 days → FAIL |
| 15 | S-08 | queue D+3 (2026-09-27) | shown [S11], parked [N01] | shown [S11, N01], parked [] | `plan_day` parks a carried item only when it overflows the cap again. On D+3 the queue has 2 items, under the cap of 10, so N01 is shown. | ENGINE_ERROR | OR-88 (D+3 + non-STRONG → PARKED, unconditional); OR-29; OR-65 |

**Summary by kind:**

- **Dimension mismatches (12, rows 1–12):** geography 10, compensation 1, employment 1.
- **Flag-only mismatch (1, row 13):** affects no Gate E metric.
- **Sequence failures (2, rows 14–15).**

Every genuine mismatch shares one pattern: the accepted 0.2.4 semantics are not reached because extraction or vocabulary misses the corpus phrasing, or, for S-08, because `plan_day` lacks the unconditional D+3 park. No mismatch traces to a rule whose semantics contradict a ruling. None was fixed in this pass.

## False EXCLUDED

| Case | Engine FAIL rule | Expected | Classification | Explained |
|---|---|---|---|---|
| **R3-005** | GEO-R03 | geography PASS, excluded false | ENGINE_ERROR | **no** |

```text
False EXCLUDED: total 1, unexplained 1  (R3-005)
```

R3-005 is a genuine engine test, and its expectation is unaffected by the overlay. The existing 0.2.4 geography implementation does not recognise "applicants resident in India are eligible" as explicit India eligibility. It applies the single-foreign-country lock (GEO-R03) and excludes the posting. This is an eligibility/safety error.

The 8 Part A false EXCLUDED cases caused by the authoring defect are now correct matches under the overlay.

## False SHORTLIST

The engine routed 7 cases to SHORTLIST: R3-032, 055, 066, 068, 087, 090 and 094. Each has these corrected expectations:

- all dimensions PASS
- `excluded = false`
- no review-routing must-have flag
- no STRETCH label

```text
False SHORTLIST: 0
```

## Sequences

| Sequence | Result | Explanation |
|---|---|---|
| S-01 | PASS | A JD-built PASS is not weakened by a search-only sighting. Newness NEW → SEEN_BEFORE. |
| S-02 | **FAIL** | ENGINE_ERROR. Expected geography FAIL / excluded at both steps, actual UNKNOWN / REVIEW. "All five working days" is not parsed. The F4 non-weakening property and newness (NEW → SEEN_BEFORE) are correct. Not a safety error. |
| S-03 | PASS | Higher-authority figure change gives UPDATED + SOURCE_CONFLICT. |
| S-04 | PASS | Lower-authority disagreement leaves the item SEEN_BEFORE, and the ATS verdicts are kept. |
| S-05 | PASS | Same-run conflicting sightings give NEW + SOURCE_CONFLICT. |
| S-06 | PASS | Owner enrichment gives employer PASS and clears `EMPLOYER_UNCLASSIFIED`. The item stays SEEN_BEFORE. |
| S-07 | PASS | Both items are IDENTITY_UNCERTAIN, shown as one grouped card using one cap slot, and neither is suppressed. |
| S-08 | **FAIL** | **ENGINE_ERROR under OR-88.** See below. |

**S-08 detail:**

- **D, D+1, D+2 (2026-09-24 to 2026-09-26):** match exactly. Each day: shown 10, carried [S11, N01], candidates 12. The OR-87 order (NEW > UPDATED > SEEN_BEFORE) is observed: new STRONG items outrank the carried ones.
- **D+3 (2026-09-27):** expected shown [S11], parked [N01]. The engine shows [S11, N01] and parks nothing.

**Effect of OR-88 on S-08.** In Part A, the D+3 divergence was SPEC_AMBIGUITY: OR-29 and OR-65 did not say whether D+3 parking applies when the queue is below the cap. OR-88 rules that it does: D+3 + non-STRONG → PARKED, regardless of capacity. The frozen S-08 expectation was already consistent with OR-88, so no sequence expectation changed. The engine behaviour also did not change. What changed is the classification: the divergence is now an ENGINE_ERROR, because 0.2.4 `plan_day` parks only carried units beyond the cap. The S-08 failure is not a safety error, since N01 is in REVIEW, neither SHORTLIST nor EXCLUDED.

## Gate R

```text
Gate R: NOT MEASURED
```

These observations are diagnostic only:

- The engine's relevance label matched every value the corpus asserts:
  - 8 posting cases
  - the 32 S-08 sequence steps
- All 7 `experience_label` assertions matched, including R3-105 STRETCH (OR-84).
- No mismatch above is relevance-driven.
- No relevance rate or score was computed.

## Integrity

- Corpus SHA verified: `25aef0e0…39cb`, `OK` before and after each run. The file is byte-identical and `blind_cases_round3.sha256` is unmodified.
- Policy hash verified: 0.2.4 = `735934bf…8136`.
- Historical policies unchanged. `git diff` is empty on `policy/`. No 0.2.5 was created.
- Engine, tests and frozen fixtures unchanged. No golden cases were added, nothing was special-cased, and no thresholds or vocabulary were changed.
- Repository changes in this pass:
  - `OWNER_RULINGS_LOG.md`: append-only, with Addendum H and OR-88.
  - This report.
- The owner-supplied overlay is untracked and was not modified.
- No network (sockets refused), no live DB (in-memory SQLite only), no `.env` or n8n, no LLM, and no application was submitted.
- No Git state mutation: no stage, commit, push, reset or checkout. HEAD and `round3-frozen` are both `5f1defc`.

## Final determination

```text
Gate E: FAIL
```

Factual basis (Part B, corrected measurement):

1. Geography accuracy is 97/107 = 90.65 %, below the 95 % threshold.
2. There is one unexplained false EXCLUDED: R3-005, ENGINE_ERROR.
3. Sequences S-02 and S-08 fail, both ENGINE_ERROR. S-08 fails under OR-88.
4. Compensation (99.07 %), employment (99.07 %), employer (100 %) and language (100 %) meet the threshold, and false SHORTLIST is 0.
