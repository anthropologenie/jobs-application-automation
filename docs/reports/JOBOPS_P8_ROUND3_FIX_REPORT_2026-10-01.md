# JobOps v2 — P8 Round-3 Fix Pass → Policy 0.2.5 (2026-10-01)

## Executive result

```text
Policy 0.2.5 implementation status:
READY FOR FRESH ROUND 4 MEASUREMENT
```

- **Not a Gate E result.** 0.2.5 has **not** been Gate E measured. Round 3 informed this fix pass, so it is now a consumed tuning and regression corpus. The acceptance measurement for 0.2.5 is a fresh, independent Round-4 holdout. That holdout was not created here, and its author must not see this report's failure list.
- **All P8 acceptance criteria (§27) hold.** See the checklist at the end.
- **Safety.** Golden, Round 1 and Round 2 have 0 new false EXCLUDED and 0 new false SHORTLIST, with zero lane changes from 0.2.4 to 0.2.5.
- **Round 3 (regression only).** False EXCLUDED went from 1 (R3-005) to 0. Dimension mismatches went from 12 to 3, and the flag-only mismatch R3-087 is resolved. S-08 now conforms to OR-88.
- **Remaining Round-3 discrepancies (R3-010, R3-012, R3-018 / S-02).** All three are intentional and pending owner open items: OI-053, OI-054 and OI-055. Each is recall-safe: UNKNOWN → REVIEW, never FAIL, never a silent PASS.
- **Default policy.** The default is still `jobops-policy@0.2.4`. 0.2.5 is registered for evaluation and replay.
  - The command says 0.2.5 becomes the default "after the acceptance criteria in §12". §12 is the location-pay task, so that cross-reference is ambiguous.
  - Earlier defaults (0.2.4, P6) were switched only after a Gate E pass, and 0.2.5's Gate E is the future Round 4.
  - The default was therefore left unchanged. Switching it is one line in `evaluation/policy_loader.py` plus the assertion in `tests/test_p8_policy_025.py::test_025_registered_but_not_default`.

## Baseline

| Item | Value |
|---|---|
| HEAD | `5f42409d66ac239680955190c222ca48c4f74c21` |
| `round3-frozen` | `5f1defc00323d7c9d906f92235108e700810d680` |
| `round3-measured-0.2.4` | `5f42409d66ac239680955190c222ca48c4f74c21` |
| Git status at start | clean |
| Baseline suite (before any change) | **2184 passed, 0 failed, 61 xfailed, 0 skipped, 0 errors** |

**Excluded from every run:** `test_p0_06_linkedin_ingestion.py`, `test_p0_07_identity_dedup.py`, `test_p0_08_review_queue.py` and `test_p0_10_time_instrumentation.py`. These open `data/jobs-tracker.db` (read-only), and this task forbids opening the live DB. They do not exercise the policy engine.

| Policy | SHA-256 before |
|---|---|
| 0.2.0 | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| 0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |
| 0.2.2 | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` |
| 0.2.3 | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` |
| 0.2.4 | `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136` |

All five matched the expected values.

## Method

- **Development.** Changes were developed in a scratch copy with no `.git`, live DB, `.env` or n8n. Each change was tested there, and the verified files were then copied into the working tree.
- **Gating.** Every new engine path is switched on only by a 0.2.5-only lexicon, parameter or queue key, so 0.2.0–0.2.4 execute the original code path. `EXTRACTOR_CODE_VERSION` is unchanged.
- **Isolation.**
  - No network: sockets are refused in tests and in the harness.
  - No LLM and no new dependencies.
  - In-memory SQLite only.
- **Task 0: Round-3 harness.** `tests/r3_blind_harness.py` is now persistent.
  - It uses the accepted Round-2 adapter unchanged (`obs_fields`, `prepare`, `project(..., "p5")`).
  - It verifies the corpus SHA before and after every replay.
  - It applies the author-correction overlay to an in-memory copy only.
  - It adds the P7b Round-3 conventions: the evaluation_date clock, each case's own fx_table, `<seq>-<observed_on>` runs, the S-06 owner enrichment, and the owner SKIPping every shown item in S-08.
  - Under 0.2.4 it reproduces P7b Part B exactly. This is asserted by `test_r3_harness_reproduces_p7b_part_b_under_024`.

## Fix table

| Fix family | Root cause (0.2.4) | Implementation (0.2.5) | New golden cases | Negative cases | Mutation test |
|---|---|---|---:|---:|---|
| India eligibility | A fixed phrase list missed forms such as "resident in India", "reserved for … who live in India" and "open to India residents". `eligibility_line` also turned *negated* or *preference* India sentences into India listing evidence, giving a silent PASS. | `lexicon.india_eligibility`, a semantic detector working per clause. It needs a place (India or worldwide), plus a subject or a direct form, plus a positive cue. Guards: negation → NEGATED; preference → INDIA_PREFERENCE (OI-053, GEO-R29 UNKNOWN). Weak statements are never listing evidence, and their India places are dropped. | 7 positive + 4 preference | 6 | 12/17 fail without the fix (7 positive, 5 negative / preference); 17/17 pass with it |
| Region / residence / authorization | No "must live in", "need to reside in", "only applicants living in", "residents of …", "US work authorization" or "authorization to work in". A lock list naming India still excluded India. Negated locks and relocations FAILed. | Broader `residence_requirement` and `work_authorization` lexicons. `lock_negation_before` and a `relocation_negation` extension. Parameter `lock_lists_including_india_do_not_exclude`. | 5 | 8 | 9/13 fail (5 positive, 4 negative); 13/13 pass |
| Office days | Missing attendance cues (building, site, workplace, hub, "at home"). "N days at the <city> office", "all five working days", "every working day" and "N days at home" were not parsed. The 3–4 day gap fell to FAIL. Weekly patterns could swallow per-month counts. | New cues and patterns, a per-month lookahead and `count_context_exclusions` (respond, notice, onboarding, training, on-call …). New rule **GEO-R28**: 3 < days/week < 4 → UNKNOWN + `HYBRID_DAYS_BETWEEN_THRESHOLDS`. | 8 positive + 6 boundary | 6 | office_days 7/11 fail; context-exclusion 3/3 fail; between-thresholds 2/6 fail (exactly 3.46 and 3.93 per week); all pass with the fix |
| Location pay | The lexicon missed "adjusted to the candidate's location", "varies based on where you live", "geographic pay" and similar. "Not adjusted by location" was read as adjusted. | Generalised `location_adjusted` patterns and `location_adjusted_negation`. COMP-R11, thresholds, FX and India-band precedence are unchanged. | 4 | 2 | 4/6 fail (3 positive, 1 negative); 6/6 pass |
| Client placement | The lexicon missed "placed full time at one of their clients", "assigned to client projects" and "employed by an employment agency". The unanchored 0.2.4 cue "deployed to clients" FAILed software ("models deployed to client environments"). "Not placed with clients" FAILed. | Person-anchored placement cues, a third-party-employer `third_party_payroll` cue, and `relationship_negation_before` (also applied inside the match). Employer and employment stay separate dimensions. | 3 | 3 | 5/6 fail (3 positive, 2 negative); 6/6 pass |
| Language preference | Hindi and other Indian languages were unknown. "X would be a plus" was not recognised. "Knowledge of X is a plus" was a weak requirement (UNKNOWN). | 12 Indian language names, more `preferred` forms, `preference_overrides_weak_requirement`. LANGUAGE_PREFERENCE stays informational (OR-81). The FAIL threshold is unchanged. | 4 | 3 | 5/7 fail (3 positive, 2 negative); 7/7 pass |
| D+3 parking | `plan_day` parked a carried item only when it overflowed the cap again. | `queue.d3_parking_unconditional`: a non-STRONG unit already carried for `review_carry_days` plans is PARKED on its next plan before the cap applies. The STRONG exemption (OR-29), carry counting (OR-65) and newness order (OR-87) are unchanged. | 5 queue scenarios + 1 newness-order test | — | Q1 (below cap) and Q2 (at cap) fail without the fix; Q3–Q5 hold either way; 5/5 pass with it; 0.2.4 reproduces the pre-OR-88 behaviour |

**Fixture.** `tests/fixtures/policy_v025_golden_cases.json` holds 69 posting cases and 5 queue scenarios.
- The wording is independent of Round 3. No R3 id and no R3 sentence is used; `test_no_round3_special_casing` checks this against production code, the 0.2.5 artifact and the fixture.
- 47 cases exercise their fix: they fail when it is removed. The other 22 are regression guards that must hold either way.

### 0.2.4 behaviours corrected by 0.2.5 (found by P8's own negative cases)

| 0.2.4 behaviour | Direction | 0.2.5 |
|---|---|---|
| "You are not required to relocate to the US" → GEO-R14 FAIL | false FAIL | PASS |
| "Must be based in India or Singapore" → GEO-R18 FAIL; "authorized to work in the US or India" → GEO-R04 FAIL | false FAIL | PASS |
| "Our models are deployed to client environments" → REL-R06 FAIL | false FAIL | PASS |
| Consultancy "you will not be placed with clients" → REL-R06 FAIL | false FAIL | PASS (employer UNKNOWN + CONSULTANCY) |
| "Hybrid setup: four days at home and one at the office" → 4 office days → FAIL | false FAIL | 1 day → PASS |
| 15 or 17 office days a month (3.46 or 3.93 per week) → FAIL | FAIL in an unruled gap | UNKNOWN (GEO-R28) |
| Plain Remote + "Candidates in India are not eligible" / "cannot apply" → India listing → PASS | false PASS | UNKNOWN |
| Plain Remote + "Candidates from India are preferred" → India listing → PASS | silent preference = eligibility | UNKNOWN (OI-053) |
| "Pay is not adjusted by location" → COMP-R11 UNKNOWN | REVIEW noise | PASS |
| "Knowledge of German would be a plus" → LANGUAGE_UNCERTAIN | REVIEW noise | PASS + LANGUAGE_PREFERENCE |

None of these behaviours occurs in the golden, Round-1 or Round-2 corpora, which is why those corpora show no lane change.

## Golden results

- **Repository suite after the change:** **2771 passed, 0 failed, 61 xfailed, 0 skipped, 0 errors** (same four live-DB files excluded).
  - That is +587 on the baseline: 315 tests in `tests/test_p8_policy_025.py` and 272 main-golden cases now also run under 0.2.5.
  - The 61 xfails are the unchanged, strict, classified Round-2 xfails.
  - The 7 git-dependent checks ran and passed in the repository.
- **Scratch-copy run:** 2764 passed, 7 skipped (git-dependent; no `.git` in scratch), 61 xfailed.
- **Main golden fixture.** `policy_v02_golden_cases.json` gained 0.2.5 following the P6 precedent:
  - 0.2.5 added to `policy_versions_under_test`;
  - the 89 cases pinned to 0.2.2–0.2.4 extended to 0.2.5;
  - the 15 `expected_by_version` cases given a 0.2.5 entry equal to their 0.2.4 entry.
  - All were verified by execution, and no existing expectation was modified.
- **P5 (`policy_v023`, 97 cases) and P6 (`policy_v024`, geography and queue) golden fixtures, plus the OR-83 owner table:** all hold under 0.2.5. This includes OD25 (structured Hybrid + every weekday → WORK_MODE_CONFLICT).

## Mutation results

Each mutation is in-memory only (`tests/p8_mutations.py`). It deep-copies the 0.2.5 document and restores the 0.2.4 data for exactly one family, which also removes the 0.2.5 key that switches its code path on. No file is written.

| Family removed | Golden cases | Pass with fix | Fail without fix | Matches recorded expectation |
|---|---:|---:|---:|---|
| india_eligibility | 17 | 17 | 12 (7 positive, 5 negative / preference) | yes |
| region_residence_authorization | 13 | 13 | 9 (5 positive, 4 negative) | yes |
| office_days | 11 | 11 | 7 (7 positive) | yes |
| office_days_context_exclusion | 3 | 3 | 3 (3 negative) | yes |
| office_days_between_thresholds | 6 | 6 | 2 (3.46 and 3.93 per week) | yes |
| location_pay | 6 | 6 | 4 (3 positive, 1 negative) | yes |
| client_placement | 6 | 6 | 5 (3 positive, 2 negative) | yes |
| language_preference | 7 | 7 | 5 (3 positive, 2 negative) | yes |
| d3_parking | 5 scenarios | 5 | 2 (below cap, at cap) | yes |

These are asserted per case by `test_mutation_removing_the_fix` and `test_or88_mutation_and_024_unchanged`.

## Before / after (0.2.4 → 0.2.5)

### Round 3 — REGRESSION ONLY (consumed corpus; frozen corpus + author-correction overlay; not a Gate E measurement)

| Metric | 0.2.4 | 0.2.5 |
|---|---:|---:|
| False EXCLUDED | 1 (R3-005) | **0** |
| False SHORTLIST | 0 | 0 |
| Dimension mismatches (cases) | 12 | 3 |
| Flag-only mismatches | 1 (R3-087) | 0 |
| REVIEW noise | 2 (R3-003, R3-033) | 0 |
| PARKED posting cases | 67 | 67 |
| Sequence overflow-PARKED | 0 | 1 (S-08 N01, OR-88) |
| Sequences passing | 6 / 8 | 7 / 8 |

**Per-dimension accuracy (diagnostic only):**

| Dimension | 0.2.4 | 0.2.5 |
|---|---:|---:|
| Geography | 97/107 | 104/107 |
| Compensation | 106/107 | 107/107 |
| Employment | 106/107 | 107/107 |
| Employer | 106/106 | 106/106 |
| Language | 105/105 | 105/105 |

**Lane changes:**
- R3-003: REVIEW → SHORTLIST
- R3-005: EXCLUDED → PARKED (geography PASS; WEAK relevance)
- R3-014: PARKED → EXCLUDED (correct FAIL)
- R3-033: REVIEW → SHORTLIST

**Genuine P7b mismatches:**

| # | Case | 0.2.4 rule | 0.2.5 rule | Status |
|---|---|---|---|---|
| 1 | R3-003 | GEO-R05 | GEO-R21 PASS | resolved |
| 2 | R3-005 | GEO-R03 FAIL | GEO-R26 PASS | resolved (the false EXCLUDED is gone) |
| 3 | R3-010 | GEO-R05 | GEO-R29 UNKNOWN | **intentional, pending OI-053** |
| 4 | R3-012 | GEO-R05 | GEO-R05 UNKNOWN | **intentional, pending OI-054** |
| 5 | R3-014 | GEO-R05 | GEO-R18 FAIL | resolved |
| 6 | R3-015 | GEO-R08 | GEO-R06 PASS | resolved |
| 7 | R3-018 | GEO-R08 | GEO-R25 UNKNOWN + WORK_MODE_CONFLICT | **intentional, pending OI-055** |
| 8 | R3-020 | GEO-R08 | GEO-R06 PASS | resolved |
| 9 | R3-033 | GEO-R08 | GEO-R06 PASS | resolved |
| 10 | R3-034 | GEO-R08 | GEO-R06 PASS | resolved |
| 11 | R3-059 | COMP-R17 | COMP-R11 UNKNOWN | resolved |
| 12 | R3-078 | REL-R01 | REL-R06 FAIL | resolved |
| 13 | R3-087 | no flag | LANG-R03 + LANGUAGE_PREFERENCE | resolved |
| 14 | S-02 | GEO-R08 | GEO-R25 UNKNOWN | **intentional, pending OI-055** (same pattern as R3-018) |
| 15 | S-08 | D+3 shows N01 | D+3 parks N01 | resolved (OR-88) |

**Why the three remaining items stay open:**
- **R3-012.** The posting names no country: plain "Remote", INR pay. OR-50 fails authorization in "the country of the posting" only when that country is other than India, and OR-66 forbids FAIL from ambiguous evidence.
  - Failing it would also FAIL the same boilerplate on Indian postings, which would be a false-EXCLUDED risk.
  - When the posting country *is* stated abroad, it already FAILs (GEO-R04).
- **R3-018 / S-02.** The text is structured "Hybrid" + "all five working days" in the building. That is structurally identical to the accepted golden OD25 (UNKNOWN + WORK_MODE_CONFLICT), while OR-15 says hybrid with 4–5 office days → FAIL.
  - The new parsing now reads the five days.
  - Choosing FAIL would change an accepted golden expectation and create new EXCLUDED outcomes, so the conflict is put to the owner.
- No remaining discrepancy is a corpus or adapter issue, and no new engine defect was found in Round 3.

### Round 1 (frozen, 144 cases + 12 sequences)

| Metric | 0.2.4 | 0.2.5 |
|---|---:|---:|
| False EXCLUDED | 0 | 0 |
| False SHORTLIST | 0 | 0 |
| Dimension mismatches | 0 | 0 |
| REVIEW noise | 0 | 0 |
| PARKED | 10 | 10 |
| Sequences failing | 0 | 0 |
| Lane changes | — | **0** |

### Round 2 (frozen, 124 cases)

| Metric | 0.2.4 | 0.2.5 |
|---|---:|---:|
| False EXCLUDED | 1 (R2-023, explained, OR-79) | 1 (same) |
| False SHORTLIST | 0 | 0 |
| Dimension mismatches | 2 (geography 122/124) | 2 (same) |
| REVIEW noise (expected lane SHORTLIST / PARKED) | 7 (pre-existing, classified relevance diagnostics) | 7 (same) |
| PARKED | 5 | 5 |
| Gate E (P6 split gates) | PASS | PASS |
| Lane changes | — | **0** |

### Golden

375 single-observation golden cases (main, P5 and P6 fixtures):

| Metric | 0.2.4 | 0.2.5 |
|---|---:|---:|
| SHORTLIST | 162 | 162 |
| EXCLUDED | 98 | 98 |
| REVIEW | 98 | 98 |
| PARKED | 17 | 17 |
| Lane changes | — | **0** |
| New false EXCLUDED | — | 0 |
| New false SHORTLIST | — | 0 |

All golden expectations pass. The new 0.2.5 golden fixture passes 69/69 cases and 5/5 queue scenarios.

## Historical policy integrity

| Policy | SHA-256 after |
|---|---|
| 0.2.0 | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| 0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |
| 0.2.2 | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` |
| 0.2.3 | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` |
| 0.2.4 | `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136` |
| **0.2.5 (new)** | `27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93` |

**0.2.0–0.2.4 are byte-identical.**
- `git diff` is empty for those files.
- Every historical golden expectation still holds under its own version.
- 0.2.5 records the 0.2.4 hash in `artifact.v0_2_4_artifact`.
- `test_025_differs_from_024_only_in_approved_places` asserts that 0.2.5 differs from 0.2.4 only in:
  - two parameters;
  - GEO-R28 and GEO-R29;
  - two review flags;
  - the listed lexicon keys;
  - three queue keys.
- Thresholds, FX settings, the language FAIL threshold and the review cap are unchanged.

## Fixture integrity

| Fixture | SHA-256 | Status |
|---|---|---|
| Round 1 `policy_v02_blind_cases.json` | `44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a` | matches its `.sha256` |
| Round 2 `policy_v02_blind_round2_cases.json` | `f54eb41bc805a28162e69e77495557b3647dd82e3b7c110c2987981edee421e5` | matches its `.sha256` |
| Round 3 `blind_cases_round3.json` | `25aef0e0c0096d31231cc8ea96ea8c4796ba981c0160daa148ebeecad7c639cb` | `sha256sum -c blind_cases_round3.sha256` → `blind_cases_round3.json: OK` before and after |
| Round 3 overlay | `886bae12aa40d7622cb0dbad0a91262068dd2112c6fc1998625832487ee5c876` | unchanged |

`blind_cases_round3.sha256` (`033a8c2e…`) and `undetermined.md` (`bc8e9001…`) are also unchanged.

## OI-053

```text
OI-053 = OPEN
```

**Question:** Does an India-resident preference/priority statement count as explicit India eligibility for geography purposes?

- It is recorded append-only in `OWNER_RULINGS_LOG.md` Addendum I and in `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` ("P8 Open"). The `RULING:` field is empty.
- Until the owner rules, a preference against a lock, APAC or an unqualified remote scope is UNKNOWN + `GEO_INDIA_PREFERENCE_UNRESOLVED` (GEO-R29) → REVIEW. It is never FAIL or EXCLUDED, and never India listing evidence.
- **R3-010 remains UNKNOWN pending OI-053.** Its lane is PARKED because its relevance is WEAK; the geography verdict is the recall-safe UNKNOWN.

Two further open items were raised so that every remaining Round-3 discrepancy has an owner question. Both are recorded the same way, with no ruling:

- **OI-054:** When a posting requires authorization to work in "the country where the job is posted" and names no country, is geography FAIL rather than UNKNOWN?
- **OI-055:** When the work mode is structured "Hybrid" and the JD states five office days, is geography FAIL (OR-15) rather than UNKNOWN + WORK_MODE_CONFLICT (OD25)?

## S-08 / OR-88

S-08 passes under 0.2.5:
- D, D+1 and D+2 match.
- On D+3 S11 (STRONG) is shown and N01 (non-STRONG) is PARKED with the queue below the cap.

The golden queue scenarios cover:
- below the cap (parked; the pre-OR-88 behaviour shows the item);
- exactly at the cap (parked; pre-OR-88 shows it);
- over the cap (parked either way);
- a STRONG item with free capacity (shown);
- D / D+1 / D+2 carry, then eligibility.

NEW > UPDATED > SEEN_BEFORE ordering is tested directly under 0.2.5.

## Architecture finding

> Do Round 2 and Round 3 together suggest that rule-based phrase extraction will continue missing novel wording on fresh holdouts?

**Yes.**
- **Round 2.** The eligibility errors were extraction and vocabulary defects (P5 report): office-day phrasing, "contract" wording, compensation layouts and language detection. They were fixed with new patterns.
- **Round 3.** It was written by a fresh author after those fixes, and the same failure class came back. All 15 genuine P7b mismatches were wording that the 0.2.4 patterns did not cover. None was a semantic disagreement with a ruling. Examples: "resident in India", "who live in India", "must live in", "two fixed days each week", "all five working days", "eleven days per month", "adjusted to the candidate's location", "placed full time at one of their clients", "Hindi is preferred".
- **This pass.** The independent negative cases written here exposed further *precision* defects in 0.2.4 phrase rules, causing false FAIL and false PASS on wording no corpus had used (see "0.2.4 behaviours corrected"). Rounds 1 and 2 changed in **zero** lanes under 0.2.5, which shows the new patterns cover wording those corpora never contained. Each holdout brings new phrasings.
- **The trigger set in P5 has been met.** The P5 report (§"recommendation" 3) said: "If a later round shows extraction long-tail failures (office-day and employment phrasing), revisit an LLM evidence extractor … with verbatim spans and no verdicts." Round 3 is that round.

**Recommendation for a separate, owner-approved architecture task (not implemented here):**
- an LLM-assisted *evidence extractor* that proposes facts (office days, eligibility scope, residence / authorization locks, placement, language preference) together with verbatim quoted spans;
- deterministic verification that each span exists verbatim in the posting and supports the fact;
- the existing deterministic policy engine keeping every verdict and threshold;
- rule extraction kept as a cross-check, with disagreement → UNKNOWN / REVIEW.

Until then, expect Round 4 to surface further wording gaps. The 0.2.5 detectors are more general (clause-level semantic cues instead of fixed phrases), but they remain patterns.

## Files changed (working tree only)

**Modified:**
- `evaluation/extract.py`, `evaluation/dimensions.py`, `evaluation/engine.py`, `evaluation/officedays.py`, `evaluation/compensation.py`, `evaluation/queue.py`, `evaluation/policy_loader.py`
- `tests/fixtures/policy_v02_golden_cases.json` (0.2.5 added to versions under test; no expectation changed)
- `OWNER_RULINGS_LOG.md` (append-only, Addendum I)
- `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` (append-only)

**New:**
- `policy/jobops-policy-0.2.5.json`
- `tests/r3_blind_harness.py`
- `tests/p8_mutations.py`
- `tests/test_p8_policy_025.py`
- `tests/fixtures/policy_v025_golden_cases.json`
- this report

## Acceptance checklist (§27)

| Criterion | Result |
|---|---|
| 0.2.0–0.2.4 unchanged | ✔ byte-identical |
| 0.2.5 general rules, no Round-3 special-casing | ✔ asserted by `test_no_round3_special_casing` |
| Golden cases for every family, with negatives | ✔ 69 cases + 5 scenarios |
| Mutation checks | ✔ all 9 mutations |
| 0 new false EXCLUDED / SHORTLIST on golden, Round 1, Round 2 | ✔ 0 lane changes |
| R3-005 no longer false EXCLUDED | ✔ |
| Governed mismatches resolved | ✔ 11 of 15 |
| S-08 conforms to OR-88 | ✔ |
| R3-010 per OI-053 | ✔ UNKNOWN |
| Remaining discrepancies explained | ✔ OI-053, OI-054, OI-055 |
| No network / live DB / LLM / new dependencies | ✔ |
| Frozen fixtures unchanged | ✔ |
| No Git state mutation | ✔ (see final verification in the session summary) |
| Round 4 | not created; no Gate E acceptance claimed for 0.2.5 |
