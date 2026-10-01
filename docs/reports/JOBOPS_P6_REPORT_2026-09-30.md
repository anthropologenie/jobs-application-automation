# JobOps P6 — Rulings catch-up, split acceptance gates, policy 0.2.4, offline real-JD replay

**Date:** 2026-09-30 · **Branch:** `jobops-v2-engine` · **HEAD (unchanged, nothing committed or staged):** `313ec4ca7b44c329ff9cc457f4259569a10e9b72`

---

## Executive Summary

**P5 diagnosis.** P5 repaired the extraction defects behind the Round-2 eligibility errors:

- language, compensation, employment, employer and flag mismatches went to 0;
- false SHORTLIST went to 0;
- 4 of 5 false EXCLUDED were fixed.

Its single aggregate gate (57/124 = 45.97 % posting mismatch) mixed those safety results with a relevance *specification* gap. 54 of the 57 remaining mismatches were STRONG/MODERATE disagreements on 8–35-word authored snippets, whose relevance was never defined in the Round-2 author sheet.

**Why aggregate relevance mismatch is no longer an acceptance gate.** OR-82 (Addendum F, F5) retires the aggregate gate. There are now two gates:

- **Gate E (eligibility and safety):** per dimension ≥ 95 %, zero unexplained false EXCLUDED / SHORTLIST, and sequences passing or explicitly classified.
- **Gate R (relevance):** measured only on owner-labelled real JDs.

This report computes **no** overall Round-2 pass/fail percentage.

**P6 objective and outcome:**

- Rulings recorded (OR-74 … OR-82).
- Round-2 re-scored under the split gates, with the 0.2.3 baseline captured before any engine change.
- `jobops-policy@0.2.4` shipped with exactly the two approved behaviour changes.
- The geography interpretation locked by tests.
- An offline real-JD replay and owner-labelling workflow built.

**Decisions:**
- **Gate E = PASS** for 0.2.4, so **0.2.4 is now the default policy** for local and replay tools. No ingestion is wired.
- **Gate R = PENDING REAL-JD LABELS.**

---

## Rulings

`OWNER_RULINGS_LOG.md` is append-only. Its prefix is byte-identical to the pre-P6 file, and a test compares it against `git show HEAD:OWNER_RULINGS_LOG.md`.

| OR | Item | Summary |
|---|---|---|
| OR-74 | OI-050 = **NO** | same-run board/ATS contradiction → NEW + SOURCE_CONFLICT → REVIEW (not UPDATED) |
| OR-75 | OI-051 = **YES** | direct contract, no duration → UNKNOWN + CONTRACT_DURATION_UNSTATED; plain Contract → FAIL |
| OR-76 | R2-075/076 | permanent EOR → UNKNOWN + EOR → REVIEW; the JD-body EOR signal counts; structured Full-time does not override it |
| OR-77 | R2-SEQ-09 | SEARCH_ONLY → FULL_JD on the same source = SEEN_BEFORE |
| (OR-63) | R2-046/051 | BELOW_TARGET and COMPENSATION_REVIEW are review flags. Already recorded, so referenced rather than duplicated. |
| OR-78 | **F1** | STRONG not redefined (≥ 3 terms / ≥ 2 clusters); no short-JD exception; relevance calibrated on owner-labelled real JDs |
| OR-79 | **F2** | single foreign-country Remote → FAIL unless India or worldwide eligibility is explicit; plain Remote / APAC → UNKNOWN |
| OR-80 | **F3** | evidence completeness has exactly two classes, missing and known; only missing counts |
| OR-81 | **F4** | informational flags never route to REVIEW alone (list locked by test) |
| OR-82 | **F5** | split acceptance gates E and R |

In `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` (append-only), OI-050, OI-051 and P5 Q1–Q4 are marked resolved, and a new item, **OI-052**, is added (see New Open Items).

---

## Historical Integrity

These hashes were identical before and after P6. They are asserted by `tests/test_p6_policy_024.py::test_frozen_artifacts_are_byte_identical`.

| Artifact | SHA-256 |
|---|---|
| `policy/jobops-policy-0.2.0.json` | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| `policy/jobops-policy-0.2.1.json` | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |
| `policy/jobops-policy-0.2.2.json` | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` |
| `policy/jobops-policy-0.2.3.json` | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` |
| Round-1 fixture `tests/fixtures/policy_v02_blind_cases.json` | `44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a` |
| Round-2 fixture (repo copy and `~/jobops-blind-round2/`) | `f54eb41bc805a28162e69e77495557b3647dd82e3b7c110c2987981edee421e5` |
| **new** `policy/jobops-policy-0.2.4.json` | `eeca4843819ef7442243500aebeec947559846535ab2c25ae2d084b7baf8e674` |
| live DB `data/jobs-tracker.db` (never opened; byte-copied only into scratch for the P0 tests) | `bf17ebb1b97dd520680e84ac695c3fd1d280694587801278598b23dca1333285` |

---

## Round-2 0.2.3 Baseline

Captured **before** any 0.2.4 engine change, with `python3 tests/r2_replay.py jobops-policy@0.2.3 --projection p6`. The `p6` projection keeps employer_type separate from employment_type. The owner-resolution overlay is applied to the four UNDETERMINED cases. FX-unscorable compensation is excluded from its denominator.

**Gate E dimensions**

| Dimension | Correct / scored | Accuracy |
|---|---|---|
| geography | 122 / 124 | 98.39 % |
| compensation | 102 / 102 (9 FX-unscorable excluded) | 100 % |
| employment_type | 122 / 122 | 100 % |
| employer_type | 124 / 124 | 100 % |
| language | 120 / 120 | 100 % |

**Safety**
- False EXCLUDED: **R2-023**.
- False SHORTLIST: none.

**Sequences:** R2-SEQ-07 fails on queue ordering. The engine counted a known consultancy UNKNOWN as incomplete evidence (pre-OR-80).

**Gate E (0.2.3):** **FAIL**. The dimensions pass. Without a classification file, R2-023 is unexplained; even with it, SEQ-07 remains an unexplained sequence failure.

**Relevance diagnostic:** 65 / 123 agree. **Lane diagnostic** (where relevance labels match): 65 / 66. **EXCLUDED vs not:** 119 / 120.

## Round-2 0.2.4

Measured with `python3 tests/r2_replay.py jobops-policy@0.2.4 --projection p6`, with classifications applied from `tests/fixtures/policy_v02_blind_round2_p6_classification.json`. Classifications label mismatches only; they never change a numerator or a denominator.

```
Gate E
  geography:        122/124 = 98.39 %   (R2-023 SUPERSEDED_RULING, R2-081 CASE_ERROR)
  compensation:     102/102 = 100 %     (9 FX-unscorable excluded: R2-023, 024, 060, 061, 062, 063, 064, 065, 075)
  employment_type:  122/122 = 100 %
  employer_type:    124/124 = 100 %
  language:         120/120 = 100 %

Safety
  false EXCLUDED:  [R2-023 — explained, SUPERSEDED_RULING]
  false SHORTLIST: []

Sequences
  10/10 pass (R2-SEQ-07 now passes)

Gate R
  relevance agreement: 65/123 — diagnostic only (1 case, R2-094, carries no relevance expectation)

Lane (diagnostic only)
  where relevance labels match: 65/66 (R2-099, SUPERSEDED_RULING)
  EXCLUDED vs not-EXCLUDED:     119/120 (R2-023)
```

## 0.2.3 → 0.2.4 Delta

An attribution check replayed all 124 postings and 10 sequences under both versions. It is asserted by `test_round2_attribution_023_to_024`, which compares projected outputs and rule ids.

- **Postings:** **zero** changes (verdicts, rule ids, flags, relevance, lane).
- **Sequences:** only **R2-SEQ-07** changed. Its day-D ordering went from `S1,S5,S3,S2,S4,M1,M3,M4,M5,M2` to `S1,S5,S2,S3,S4,M1,M3,M2,M4,M5`, which matches the corpus. The consultancy UNKNOWN is `known`, so S2 and M2 (complete, Bengaluru hybrid) now rank above S3, M4 and M5 (salary undisclosed, `missing`).
- **Change B (geography):** changes no Round-2 posting, because none states explicit India/worldwide eligibility. It is exercised by 16 new golden cases and 7 mutation pairs.
- **Historical golden set under 0.2.4:** identical to 0.2.3 (272 cases; G072 stays pinned to 0.2.0–0.2.2).
- **P5 golden cases (97):** identical outcomes under 0.2.3 and 0.2.4.
- **Unexpected changes:** none.
- **Policy-level difference from 0.2.3:** exactly `artifact`, `parameters` (+ `completeness_counts_missing_only`), `rules` (+ `evidence_gap` tags, + GEO-R26 / GEO-R27), `queue` (a note), and `lexicon` (+ `explicit_eligibility`). This is asserted by `test_024_differs_from_023_only_in_approved_places`. `relevance` is unchanged (`test_relevance_definition_unchanged_from_023`).

**Bug recorded (Change B):** under 0.2.3, "Remote — Canada" plus "Candidates in India are welcome" / "Worldwide candidates are eligible" stayed FAIL (GEO-R03), because the explicit eligibility statement was never considered against the remote statement's country. This is fixed in 0.2.4 (GEO-R26). "Work from anywhere in the world" already passed in 0.2.3 (GEO-R01, worldwide place).

---

## Mismatch Classification

Every remaining Round-2 mismatch under 0.2.4 is classified in `tests/fixtures/policy_v02_blind_round2_p6_classification.json`, with evidence, rule and disposition. Each is also a strict xfail (`reason="<CLASS>:<id> — <rule>"`) in `tests/test_policy_v02_blind_round2_p6.py`. **No mismatch is an ENGINE_BUG.**

| Case(s) | Facet | Quoted evidence | Applicable rule | Class | Disposition |
|---|---|---|---|---|---|
| R2-023 | geography, false EXCLUDED | location `Remote — Canada`; no India/worldwide statement | Round-2 sheet §3 "foreign-only listing with no India eligibility evidence → UNKNOWN" is superseded by **OR-79**: "A remote posting naming a single foreign country … is a region lock → FAIL" | **SUPERSEDED_RULING** | Engine correct; explained false EXCLUDED (OR-82: following an owner ruling is not an engine false exclusion). Fixture unchanged. |
| R2-081 | geography | location `Remote`, work mode `Work from Home`; JD has no India and no region | The Round-2 sheet itself says "remote with no region and no India listing → UNKNOWN"; OR-38; **OR-79** "Plain Remote … → UNKNOWN" | **CASE_ERROR** | The expected PASS contradicts the case's own rulings sheet. The lane is EXCLUDED either way (EMP-R04 contract-to-hire, as expected). |
| R2-099 | lane | "9+ years of software/QA experience, including 2+ with LLM systems" | **OR-68 (E3)**: "If experience is classified STRETCH it routes to REVIEW" | **SUPERSEDED_RULING** | REVIEW is correct. |
| R2-006, 012, 016, 017, 023, 024, 028, 029, 032, 034, 036, 040, 041, 042, 043, 045, 047, 051, 052, 056, 057, 058, 059, 060, 062, 063, 064, 065, 066, 070, 074, 075, 077, 078, 079, 081, 084, 085, 086, 087, 088, 089, 090, 091, 092, 093, 095, 096, 101, 111, 113, 117, 118, 119, 120, 121, 123, 124 (58) | relevance | e.g. R2-077 "Build LLM-based underwriting assistants and evals." → MODERATE (2 terms) | Round-2 sheet §16 defines labels but no threshold; **OR-78**: "STRONG remains ≥ 3 distinct AI-specific terms across ≥ 2 capability clusters … no short-JD exception … Round-2 relevance expectations … are diagnostic only" | **SPEC_AMBIGUITY** | Diagnostic only; Gate R uses owner-labelled real JDs. No threshold or vocabulary change (OR-78). R2-101 (expected MODERATE, engine STRONG: "evaluation of LLM rerankers" = 3 terms / 3 clusters) meets the OR-78 definition literally. |
| R2-023, 024, 030, 032, 036, 060, 061, 062, 063, 064, 065, 075, 080, 120, 121 (15) | FX | foreign-currency salary with `fx_snapshot_age_days` but no rate | OR-27 / OR-37: foreign figures need an owner-maintained dated FX snapshot; P6 §26 "Do not invent FX rates" | **ADAPTER_LIMIT** | Compensation and FX flags are excluded from Gate E denominators and listed. R2-065 (US band + "adjusted to the candidate's location") would have matched on COMP-R11 without FX; the harness excludes every non-INR figure without an India band, conservatively. |

The P6 per-case suite for Round 2 has 322 passes and 61 strict xfails (2 geography + 58 relevance + 1 lane). All 10 sequences pass.

## False EXCLUDED

| Case | Evidence | Rule | Disposition |
|---|---|---|---|
| R2-023 | `Remote — Canada` | GEO-R03 (OR-50, OR-79) | **Explained**, SUPERSEDED_RULING. Not an engine defect. |

There are zero unexplained false EXCLUDED.

## False SHORTLIST

None. There were none under 0.2.3 either; R2-025 was fixed in P5.

## Gate E

**PASS.** Detail:

| Dimension | Accuracy |
|---|---|
| geography | 98.39 % |
| compensation | 100 % (9 FX-unscorable excluded) |
| employment_type | 100 % |
| employer_type | 100 % |
| language | 100 % |

- Zero unexplained false EXCLUDED.
- Zero unexplained false SHORTLIST.
- Sequences 10/10.

The full suite is green and 0.2.0–0.2.3 are byte-identical. Therefore `evaluation.policy_loader.DEFAULT_VERSION = "jobops-policy@0.2.4"`. 0.2.3 was never the default.

## Gate R

**PENDING REAL-JD LABELS.** There are no owner-labelled real JDs in the repository. Round-2 relevance (65 / 123) is diagnostic only and is never owner truth.

## Replay Tool

1. `python3 tools/replay_real_jds.py data/real_jds/batch1/ --as-of 2026-10-01` (a folder of `.txt` files: title on line 1).
2. `python3 tools/replay_real_jds.py export.json --mapping my_mapping.json --as-of 2026-10-01 --out data/replay/run1` (JSON or CSV; start from `tools/replay_mapping.example.json`).
3. Add `--fx data/fx/fx_rates.csv` (copy of `data/fx/fx_rates.template.csv`) and/or `--policy jobops-policy@0.2.3`.
4. Read `data/replay/run1/digest.md`, starting with the **EXCLUDED AUDIT**. Fill `owner_labels.csv` (the owner columns start empty).
5. `python3 tools/score_owner_labels.py data/replay/run1/owner_labels.csv --out data/replay/run1/score.md`.

## Test Totals

Full suite in the scratch copy, with P0 tests on a byte copy of the DB:

| Result | Count |
|---|---|
| passed | **2409** |
| failed | **0** |
| xfailed | **61** (all strict, all Round-2 classified, in `test_policy_v02_blind_round2_p6.py`) |
| xpassed | **0** |
| skipped | **7** (see below) |
| errors | **0** |

The 7 skips are the git-dependent checks (`.gitignore` coverage ×6 and the rulings append-only check ×1). The scratch copy has no `.git`, so they skip there. They were run separately in the repository: **7 passed**.

| Group | Tests |
|---|---|
| Original P0 (unchanged) | 363 |
| Golden 0.2.0 / 0.2.1 / 0.2.2 / 0.2.3 / 0.2.4 | 184 / 184 / 273 / 272 / 272 (+1 shape) |
| `test_p1a_policy_021` / `test_p3_policy_022` | 50 / 27 |
| `test_p5_policy_023` | 129 |
| `test_p6_policy_024` | 58 + 1 skip (in the scratch copy) |
| `test_policy_v02_blind_round2_p6` | 322 + 61 xfailed |
| `test_p6_replay_tools` | 9 + 6 skips (in the scratch copy) |
| Round-1 blind (0.2.2, pinned) | 158 |
| Other v0.2 unit and support modules | 107 |

**Round-1 replay:** 144/144 cases and 12/12 sequences under both 0.2.2 and 0.2.4.

**Historical-test changes, both documented and ruling-driven:**
- `tests/test_v02_guardrails.py`: the default-version guard now asserts 0.2.4, exactly as P1a and P3 did for their promotions.
- `tests/test_v02_policy_engine.py::test_heuristic_detection_never_reaches_fail_confidence`: pinned to 0.2.2, the policy whose stop-word heuristic it describes. OR-69 (E4) replaced that detector. Its assertion is unchanged. The 0.2.4 counterpart is `test_german_jd_fails_under_024_detector`.

**Golden fixture:** `tests/fixtures/policy_v02_golden_cases.json` gained 0.2.4 entries, additive only. A programmatic check confirms no existing expectation changed.

## Mutation Tests

- **P6 geography (7 pairs):**
  - Canada vs + India welcome (FAIL→PASS)
  - Remote vs + India eligible (UNKNOWN→PASS)
  - EMEA vs + India eligible (FAIL→UNKNOWN)
  - APAC vs + India eligible (UNKNOWN→PASS)
  - India welcome vs + work authorization in Canada (PASS→FAIL)
  - "office in India" vs "India candidates welcome" (FAIL→PASS)
  - Germany vs + worldwide (FAIL→PASS)
- **P6 queue (2):**
  - consultancy vs missing salary flips the order;
  - re-tagging one rule's `evidence_gap` in a variant policy flips the order, which proves the tags drive ordering.
- **P6 drift guards (3):** a third evidence class, an untagged UNKNOWN rule, or a tag on a PASS rule is each rejected at load.
- **P5 mutation pairs (15):** still passing.

## Real-JD Workflow

The workflow is replay → digest → owner labelling → scorer. It is documented in `docs/architecture/JOBOPS_V2_REAL_JD_REPLAY.md`.

- **Replay** runs entirely offline, on an in-memory DB built by the migration runner. A test enforces that only `:memory:` is opened. There is no network access (sockets refused in tests), no LLM, and nothing is submitted.
- **Digest:**
  - per posting: lane and its reason, relevance with term evidence, verdicts for geography, compensation, employment, employer and language, each with a verbatim span and rule id, experience, and flags;
  - the mandatory `## EXCLUDED AUDIT`: posting, title, company, failing dimension, FAIL, exact evidence span and rule.
- **`owner_labels.csv`:** has empty `owner_relevance` / `owner_eligibility` / `owner_lane` columns.
- **`tools/score_owner_labels.py`** reports:
  - the relevance confusion matrix, STRONG precision and recall, MODERATE / WEAK agreement, and disagreement examples;
  - eligibility agreement (per dimension when the owner adds those columns);
  - EXCLUDED and PARKED cross-tabs;
  - the safety rows (engine EXCLUDED but owner eligible; engine SHORTLIST but owner ineligible);
  - JD-length quartiles and median length by owner relevance, labelled as not causal.
  - There is no composite score.
- **FX:** no rates ship with the tool. Without `--fx`, a foreign-only salary is UNKNOWN + FX_RATE_UNAVAILABLE (tested).
- **Data protection:** `.gitignore` excludes `data/replay/`, `data/real_jds/`, `data/jds/`, `*owner_labels*.csv`, `*.jd.txt` and `scraped_jds/` (verified with `git check-ignore`).

## Remaining Risks (measured)

- **Round-2 relevance agreement is 65/123**, entirely classified SPEC_AMBIGUITY. How good relevance really is remains unknown until owner-labelled real JDs are scored (Gate R).
- **FX:** 15 Round-2 cases can't be scored for compensation because no owner rates exist. R2-065 is excluded conservatively even though it is determinable without FX.
- **Geography:** 2/124 mismatches, both classified. The multi-region + explicit-India combination is open (OI-052), with a temporary recall-safe UNKNOWN.
- **Queue ordering:** the missing/known tags are an interpretation of OR-80 applied to 34 UNKNOWN rules. Examples: LANG-R05 (detector uncertainty) and COMP-R04 (range straddling the floor) are tagged `known`; COMP-R14 / R19 (FX unavailable or stale) are tagged `missing`. Each tag is in the artifact and locked by tests; the owner can re-tag without code changes.

## New Open Items

- **OI-052:** When a remote posting names a multi-country region that excludes India (e.g. "Remote — EMEA") but the JD explicitly states that candidates in India are eligible, should geography be PASS rather than UNKNOWN? Yes or no.
  - **Temporary behaviour:** UNKNOWN + GEO_REGION_AMBIGUOUS → REVIEW (GEO-R27). This is the recall-safe reading: never FAIL, never a silent PASS.

## Git Status

`git status --short`, taken after all P6 work:

```
 M .gitignore
 M OWNER_RULINGS_LOG.md
 M company/registry.py
 M docs/architecture/JOBOPS_V2_OPEN_ITEMS.md
 M evaluation/compensation.py
 M evaluation/dimensions.py
 M evaluation/engine.py
 M evaluation/extract.py
 M evaluation/newness.py
 M evaluation/policy_loader.py
 M evaluation/queue.py
 M evaluation/selection.py
 M evaluation/service.py
 M relevance/labeller.py
 M tests/fixtures/policy_v02_golden_cases.json
 M tests/test_v02_guardrails.py
 M tests/test_v02_policy_engine.py
 M tests/test_v02_store_migrations.py
?? data/fx/
?? docs/architecture/JOBOPS_V2_REAL_JD_REPLAY.md
?? docs/reports/JOBOPS_BLIND_ROUND2_REPORT_2026-09-30.md
?? docs/reports/JOBOPS_P5_FIX_REPORT_2026-09-30.md
?? docs/reports/JOBOPS_P6_REPORT_2026-09-30.md
?? evaluation/officedays.py
?? policy/jobops-policy-0.2.3.json
?? policy/jobops-policy-0.2.4.json
?? store/migrations/0103_third_party_payroll_classification.sql
?? tests/fixtures/policy_v023_golden_cases.json
?? tests/fixtures/policy_v024_golden_cases.json
?? tests/fixtures/policy_v02_blind_round2_cases.json
?? tests/fixtures/policy_v02_blind_round2_cases.sha256
?? tests/fixtures/policy_v02_blind_round2_owner_resolutions.json
?? tests/fixtures/policy_v02_blind_round2_p4b_raw_022.json
?? tests/fixtures/policy_v02_blind_round2_p6_classification.json
?? tests/fixtures/policy_v02_blind_round2_undetermined.md
?? tests/r2_blind_harness.py
?? tests/r2_replay.py
?? tests/test_p5_policy_023.py
?? tests/test_p6_policy_024.py
?? tests/test_p6_replay_tools.py
?? tests/test_policy_v02_blind_round2_p6.py
?? tools/replay_mapping.example.json
?? tools/replay_real_jds.py
?? tools/score_owner_labels.py
```

The modified and new files above include the P5 work, which was also uncommitted. Nothing was committed, staged or branched.

No network was used, the live DB was never opened or modified (hash unchanged), no dependency was added, and no ingestion, C1/C2 or LLM work was started. Application submission remains human-only.

---

## Post-P6 note (appended 2026-09-30) — OI-052 resolved

This note does not change the P6 results above, which are historical: Gate E = PASS measured on the P6 build of 0.2.4 (`eeca4843…e674`), and Gate R = PENDING REAL-JD LABELS.

After P6, the owner resolved **OI-052 = YES** (**OR-83**): explicit India/worldwide eligibility overrides a multi-country region label that would otherwise exclude India. In `jobops-policy@0.2.4`, GEO-R27 changed from UNKNOWN + GEO_REGION_AMBIGUOUS to **PASS**. Nothing else in the policy changed except the artifact authority and change text.

- The updated 0.2.4 SHA-256 is `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136`.
- No Round-2 posting states explicit India/worldwide eligibility, so the Round-2 replay is unaffected.
- 0.2.0–0.2.3 and both blind fixtures are byte-identical.
