# JobOps v2 — P8b: OI-053..OI-055 Resolution → Policy 0.2.6 (2026-10-01)

## Result

```text
READY FOR FRESH ROUND 4 MEASUREMENT
```

- **Rulings.** The owner rulings are recorded as OR-89 (OI-053), OR-90 (OI-054) and OR-91 (OI-055).
- **0.2.6 was necessary.** OI-053 and OI-055 change production behaviour. OI-054 does not: 0.2.5 already behaves as ruled.
- **0.2.6 is a narrow governance release.** It is 0.2.5 plus those two rulings and nothing else.
- **Historical policies.** 0.2.0–0.2.5 are byte-identical.
- **Default.** The default is still `jobops-policy@0.2.4`. 0.2.6 is registered for evaluation and replay only, and no default switch was needed for the tests.
- **No Gate E claim.** Gate E was not measured and Round 4 was not created or run.

## Baseline

| Item | Value |
|---|---|
| HEAD | `b5198feb9d81d577ca1123193be5830281897697` (P8 / policy 0.2.5) |
| Branch | `jobops-v2-engine`, up to date with `origin/jobops-v2-engine` |
| Working tree | clean |
| 0.2.5 SHA-256 | `27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93` (as expected) |
| Round-3 corpus | `sha256sum -c blind_cases_round3.sha256` → `OK` |

## Rulings

| OI | Decision | Behaviour change? | Policy |
|---|---|---|---|
| OI-053 | YES — an India preference / priority is explicit India eligibility; it never overrides an explicit exclusion | **Yes** | OR-89 → 0.2.6 |
| OI-054 | UNKNOWN → REVIEW for an unnamed posting country | **No** (already 0.2.5) | OR-90 → 0.2.5 and 0.2.6 |
| OI-055 | FAIL for an explicit 4–5 office days with structured Hybrid; supersedes OD25 | **Yes** | OR-91 → 0.2.6 |

All three are recorded append-only:
- `OWNER_RULINGS_LOG.md`, Addendum J, entries 86–88. Addendum I, which holds the open questions, is untouched.
- `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md`, "P8b Resolved" table.

### Implementation (0.2.6 only; every path gated on a 0.2.6-only key)

**OR-89 — India preference as eligibility**
- Parameter `india_preference_is_eligibility`: `summarize_geography` treats INDIA_PREFERENCE as eligibility. It lifts:
  - a single-country lock (GEO-R26);
  - a multi-country lock (GEO-R27);
  - APAC or plain Remote (GEO-R26).
- `india_eligibility.precedence = [INDIA, WORLDWIDE, NEGATED, INDIA_PREFERENCE]`: a negated India clause in the same sentence outranks a preference.
- Foreign residence and authorization locks are earlier FAIL rules, so they keep precedence unchanged.
- `india_place` gains "India/Indian candidates|applicants|engineers|developers|talent|professionals". Without it, the ruling's own example "India candidates are preferred" was not detected at all under 0.2.5 (APAC stayed GEO-R05).
- GEO-R29 is kept, now unreachable, so the rule table remains a superset of 0.2.5.

**OR-91 — explicit office days over the Hybrid label**
- Parameter `office_days_override_hybrid_label`: when a Hybrid statement is present, an ONSITE statement derived from a measurable office-day count is read as the hybrid's office days. Bengaluru Hybrid + 4 or 5 days → GEO-R07 FAIL.
- These still stay WORK_MODE_CONFLICT (GEO-R25):
  - a bare "on-site" with no count;
  - structured Remote + five office days (OR-71).
- Attendance with no count ("may occasionally be required") stays GEO-R08 UNKNOWN.

**OR-90 — unnamed posting country**
- No code or policy-data change.
- An unnamed country gives GEO-R05 UNKNOWN → REVIEW.
- A named foreign country gives GEO-R04 FAIL.
- India is never failed.
- The country is inferred only from the posting's own location, via the accepted OR-50 / 0.2.1 listing fallback.

**`0.2.6` vs `0.2.5`**, asserted by `test_026_differs_from_025_only_in_approved_places`:
- the artifact metadata;
- two parameters;
- `lexicon.india_eligibility` (`india_place`, `precedence`, `note`);
- notes and ruling references on GEO-R05, R07, R25 and R29.

Rule predicates, flags, queue, relevance, compensation, FX, employment and employer sections are identical.

## Tests

### Focused P8b tests (`tests/test_p8b_policy_026.py`): 260 passed

**Ruling cases** (`tests/fixtures/policy_v026_golden_cases.json`, 20 cases):

| Case | Text | 0.2.6 result |
|---|---|---|
| B53-01 | Remote + "India residents are our priority." | PASS GEO-R26 |
| B53-02 | APAC + "India candidates are preferred." | PASS GEO-R26 |
| B53-03 | Germany + "India-based applicants are given priority." | PASS GEO-R26 |
| B53-04 | EMEA + "India residents are given priority for this role." | PASS GEO-R27 |
| B53-N1 | "India candidates are preferred, but applicants must reside in the US." | FAIL GEO-R18, EXCLUDED |
| B53-N2 | Germany + "India preferred, but candidates in India are not eligible." | FAIL GEO-R03, EXCLUDED |
| B53-N3 | Germany + "India candidates are preferred, but candidates in India are not eligible." | FAIL GEO-R03, EXCLUDED |
| B53-N4 | Remote + "India preferred, but candidates in India are not eligible." | UNKNOWN GEO-R05 (never PASS) |
| B54-01 | "authorized to work in the country where the job is posted", no country | UNKNOWN GEO-R05, REVIEW |
| B54-02 | "… in the United States" | FAIL GEO-R04, EXCLUDED |
| B54-03 | Remote — India + "… in India" | PASS GEO-R02 |
| B54-04 | Remote + "… in India" | UNKNOWN GEO-R05 (not FAIL; unchanged from 0.2.5) |
| B55-01 | Hybrid + "five days a week" in the office | FAIL GEO-R07, EXCLUDED |
| B55-02 | Hybrid + "five days per week" at the Bengaluru office | FAIL GEO-R07, EXCLUDED |
| B55-03 | Hybrid + "all five working days" at the campus | FAIL GEO-R07, EXCLUDED |
| B55-04 | Hybrid + "four days a week" | FAIL GEO-R07, EXCLUDED |
| B55-N1 | Hybrid + "Office attendance may occasionally be required." | UNKNOWN GEO-R08 |
| B55-N2 | Hybrid + "This is an on-site role." | UNKNOWN GEO-R25 |
| B55-N3 | Remote + five days at a Chennai centre | UNKNOWN GEO-R25 (OR-71) |
| B55-N4 | Hybrid + 2 days | PASS GEO-R06 |

**Regression coverage in the same module:**
- **Historical golden fixtures under 0.2.6:** P5 (97), P6 geography (23), P8 (69 + 5 queue scenarios) and the OR-83 owner table (11) all hold. The only exceptions are the four supersessions below.
- **Round 1 and Round 2:** zero lane changes from 0.2.5 to 0.2.6, and Round-2 Gate E still passes.
- **Integrity:** 0.2.0–0.2.5 hashes, the 0.2.6 approved-diff check, the default unchanged, and the rulings / open-items records.

### OD25 and other supersessions (§10)

No historical expectation was edited. `policy_v026_golden_cases.json` → `supersessions` lists each superseded case with:
- its historical expectation, copied verbatim;
- the versions that expectation still governs;
- the superseding ruling and the reason;
- the expectation from 0.2.6 on.

`test_supersession_is_auditable` checks both sides: the old expectation under the old versions and the new expectation under 0.2.6.

| Case | Historical expectation (still governs) | From 0.2.6 | Ruling |
|---|---|---|---|
| OD25 (`policy_v023_golden_cases.json`) | UNKNOWN + WORK_MODE_CONFLICT (0.2.3–0.2.5) | FAIL GEO-R07, EXCLUDED, no WORK_MODE_CONFLICT | OR-91 |
| P8-PRF-01, 02, 03 (`policy_v025_golden_cases.json`) | UNKNOWN GEO-R29, REVIEW (0.2.5) | PASS GEO-R26, SHORTLIST | OR-89 |

P8-PRF-04 (India listing + preference → PASS) is unaffected.

### Mutation results (§12)

In memory only (`tests/p8b_mutations.py`):

| Mutation | Cases checked | Fail without the ruling | Hold either way |
|---|---:|---|---|
| OR-89 (preference-as-eligibility removed) | 7 | 4: B53-01..04 revert to UNKNOWN (GEO-R29, or GEO-R05 for B53-02) | the three exclusion cases (FAIL / UNKNOWN unchanged) |
| OR-89-precedence (exclusion guard removed) | 1 | B53-N3 becomes a wrongful **PASS / SHORTLIST** | — |
| OR-91 (count-over-label removed) | 8 | 3: B55-01..03 revert to UNKNOWN GEO-R25 | B55-04 (4 days already FAIL) and the four ambiguity negatives |
| OR-90 | — | not applicable: no production behaviour change | — |

`test_every_mutation_is_exercised` asserts that every defined mutation is exercised.

### Full regression (§13)

Command: `python3 -m pytest tests -q --ignore=…p0_06 … --ignore=…p0_10`, run in the repository.

| Result | Count |
|---|---:|
| passed | **3303** |
| failed | **0** |
| xfailed | 61 (the unchanged, strict, classified Round-2 xfails) |
| skipped | 0 |
| errors | **0** |

- The P8 checkpoint ran 2771 passed + 61 xfailed. The difference is +260 P8b tests and +272 main-golden cases now also run under 0.2.6.
- **Main golden fixture.** 0.2.6 was added to `policy_versions_under_test`; 89 pinned cases and 15 `expected_by_version` entries were extended with their 0.2.5 expectation. All pass, so no main-golden case changes under 0.2.6, and no existing expectation was modified.
- **Excluded tests.** The four P0 tests stay excluded because they read `data/jobs-tracker.db`.

**Lane comparison, 0.2.5 → 0.2.6:**

| Corpus | Lane changes |
|---|---|
| Round 1 | 0 |
| Round 2 | 0 |
| Golden (375 cases) | 1: OD25 REVIEW → EXCLUDED (the ruled OR-91 supersession) |

There are no new false EXCLUDED and no new false SHORTLIST.

## Round 3 (regression only; frozen corpus + overlay unchanged)

| Item | 0.2.5 | 0.2.6 |
|---|---|---|
| R3-010 | UNKNOWN GEO-R29 (OI-053 pending) | **PASS GEO-R26: resolved by OI-053** |
| R3-012 | UNKNOWN GEO-R05, REVIEW-class | **UNKNOWN GEO-R05: correct under OI-054** (the corpus' FAIL expectation is superseded by OR-90) |
| R3-018 | UNKNOWN GEO-R25 (OI-055 pending) | **FAIL GEO-R07, EXCLUDED: resolved by OI-055** |
| S-02 | FAIL (geography UNKNOWN at both steps) | **PASS: resolved by OI-055** |
| Geography | 104/107 | 106/107 (only R3-012, by ruling) |
| False EXCLUDED / SHORTLIST | 0 / 0 | 0 / 0 |
| Sequences | 7/8 | **8/8** |

R3-012 is PARKED rather than REVIEW because its relevance is WEAK; its geography verdict is the ruled UNKNOWN. The Round-3 corpus, `.sha256`, `undetermined.md` and the overlay were not modified (`OK` after the run).

## Historical integrity

| Policy | SHA-256 |
|---|---|
| 0.2.0 | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| 0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |
| 0.2.2 | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` |
| 0.2.3 | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` |
| 0.2.4 | `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136` |
| 0.2.5 | `27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93` (unchanged) |
| **0.2.6 (new)** | `de527c5d1dceb400913ec42e5aa527f19cd809e5054fcef5c61337d7fb890455` |

0.2.0–0.2.5 are byte-identical. 0.2.6 records the 0.2.5 hash in `artifact.v0_2_5_artifact`.

## Files changed (working tree only)

**Modified:**
- `evaluation/extract.py` (configurable eligibility precedence)
- `evaluation/dimensions.py` (OR-89, OR-91)
- `evaluation/engine.py` (passes the two 0.2.6 parameters)
- `evaluation/policy_loader.py` (registers 0.2.6; the default stays 0.2.4)
- `tests/fixtures/policy_v02_golden_cases.json` (0.2.6 added under test)
- `OWNER_RULINGS_LOG.md` (append-only, Addendum J)
- `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` (append-only, P8b Resolved)

**New:**
- `policy/jobops-policy-0.2.6.json`
- `tests/fixtures/policy_v026_golden_cases.json`
- `tests/p8b_mutations.py`
- `tests/test_p8b_policy_026.py`
- this report

## Round 4 readiness

```text
READY FOR FRESH ROUND 4 MEASUREMENT
```

- **Basis:** every test and integrity check passes, and OI-053, OI-054 and OI-055 are closed by owner rulings.
- **Measurement target:** the fresh Round-4 holdout should be measured against `jobops-policy@0.2.6`.
- **Not claimed:** no Gate E pass is claimed, and Round 4 was not created or run.
